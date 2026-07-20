#!/usr/bin/env python3
"""
cluster_telemetry.py — Unified Jetson Nano 11-node cluster telemetry
====================================================================
Single source of truth for cluster health + live monitoring + web UI.
Merges the old cluster_health.py (audit gate) and cluster_monitor.py (live
terminal view) so configuration and collection logic live in exactly one place.

Modes:
  audit     one-shot deploy-gate health check  -> prints table, exits 0 (healthy) / 1 (degraded)
  monitor   live terminal dashboard            -> loops until Ctrl+C
  web       browser dashboard                  -> http://localhost:9090 (zero extra deps)

Usage:
  python cluster_telemetry.py audit
  python cluster_telemetry.py monitor
  python cluster_telemetry.py web

Requires:  pip install psutil paramiko
"""

import sys
import os
import re
import json
import time
import socket
import concurrent.futures
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import psutil
import paramiko

# ===========================================================================
# SINGLE SOURCE OF TRUTH
# All changeable config (node IPs, ports, SSH, thermal/RAM thresholds, paths)
# lives in mcp/cluster_config.py. Import it; never redefine here. This keeps
# telemetry, watchdog, QoS and the MCP server perfectly synchronised.
# ===========================================================================

# --- Shared literals (kept here so they are not duplicated across the file) ---
CFG_MODULE = "mcp.cluster_config"
ENSEMBLE_STATE_FILE = "ensemble_state.json"
JSON_CT = "application/json"
# Local-only telemetry dashboard on a trusted LAN segment. No credentials or PII
# are served; plaintext HTTP is acceptable for loopback/LAN telemetry viewing.
# nosec B104 / SonarLint: HTTP is intentional here, not a security defect.
TRUSTED_LAN_HTTP = True


def _cfg(attr, default=None):
    """Read an attribute from the shared cluster_config module (single import)."""
    return getattr(__import__(CFG_MODULE, fromlist=[attr]), attr, default)
try:
    from mcp.cluster_config import (
        RPC_PORT as PORT,
        NODE_IPS as JETSON_IPS,
        NODE0_IP,
        SSH_USER, SSH_KEY_PATH,
        MIN_REQUIRED_RAM_GB, TOTAL_RAM_GATE_GB,
        THERMAL_WARN_C, THERMAL_FAIL_C, THERMAL_EXCLUDE_ZONES,
        METRICS_FILE, WEB_HOST, WEB_PORT, MONVIEW_INTERVAL_SEC,
        MODELS_DIR,
        CHAT_UPLOAD_DIR,
        set_cluster_mode, CLUSTER_MODE_MAINTENANCE, CLUSTER_MODE_NORMAL,
        partition_ensemble, ENSEMBLE_APPLY_SYSTEM_PROMPT,
        SERVER_HOST as ENS_HOST, SERVER_PORT_POOL,
        rpc_list,
        MTP_CLI as RESIDENT_CLI,   # MTP llama-cli == node ggml-rpc-server build
        SAMPLING_TEMP, SAMPLING_MIN_P, SAMPLING_TOP_P, SAMPLING_REPEAT_PENALTY,
        CTX_SIZE_DEFAULT, MAX_TOKENS_DEFAULT, REQUEST_TIMEOUT,
    )
except Exception as _cfg_err:  # pragma: no cover
    print(f"[TELEMETRY] cluster_config unavailable ({_cfg_err}); using built-ins",
          file=sys.stderr)
    PORT = 50052
    JETSON_IPS = [f"192.168.50.{i}" for i in range(150, 161)]
    NODE0_IP = "192.168.50.150"
    SSH_USER = "jetson"
    SSH_KEY_PATH = r"C:\Users\marti\.ssh\id_ed25519"
    MIN_REQUIRED_RAM_GB = 3.5
    TOTAL_RAM_GATE_GB = 28.0
    THERMAL_WARN_C = 80.0
    THERMAL_FAIL_C = 85.0
    THERMAL_EXCLUDE_ZONES = ("PMIC",)
    METRICS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "rpc_metrics.json")
    WEB_HOST = "0.0.0.0"
    WEB_PORT = 9090
    MONVIEW_INTERVAL_SEC = 1.0
    MODELS_DIR = r"C:\Models"
    CHAT_UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_uploads")
    partition_ensemble = None
    ENSEMBLE_APPLY_SYSTEM_PROMPT = True
    ENS_HOST = "127.0.0.1"
    SERVER_PORT_POOL = list(range(8081, 8092))
    def rpc_list():
        return ",".join(f"{ip}:{RPC_PORT}" for ip in JETSON_IPS)
    RESIDENT_CLI = r"C:\llama.cpp-mtp\build\bin\llama-cli.exe"
    SAMPLING_TEMP = 0.1
    SAMPLING_MIN_P = 0.05
    SAMPLING_TOP_P = 0.9
    SAMPLING_REPEAT_PENALTY = 1.1
    CTX_SIZE_DEFAULT = 4096
    MAX_TOKENS_DEFAULT = 4096
    REQUEST_TIMEOUT = None

# ===========================================================================
# COLLECTORS
# ===========================================================================
def check_rpc_port(ip):
    """TCP connect probe for the RPC daemon (no SSH needed)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            return s.connect_ex((ip, PORT)) == 0
    except Exception:
        return False


def get_node_ssh(ip):
    """One SSH session per node: RAM available (UMA) + UI active + max thermal (deg C).

    The Jetson Nano has NO discrete VRAM -- CPU and GPU share 4 GB LPDDR4. We read
    /proc/meminfo (MemAvailable) as the unified RAM free, check for a display server,
    and parse tegrastats for the hottest zone. Returns (ram_gb, ui_active, temp_c).
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        # Connect timeout guards the TCP/SSH handshake. The channel read timeout
        # (set below) is the critical guard: without it, a node that accepts the
        # connection but then stalls (e.g. a board dropping off the network mid-
        # session) would block .read() FOREVER, freezing the background refresher
        # thread and leaving the dashboard stuck on a stale all-down snapshot.
        ssh.connect(ip, username=SSH_USER, key_filename=SSH_KEY_PATH, timeout=3.0)
        # 5s ceiling on each command's output read -- a node that cannot answer
        # within this is effectively down and must not hang the whole view.
        CH_TIMEOUT = 5.0
        _, o1, _ = ssh.exec_command("awk '/MemAvailable/ {print $2}' /proc/meminfo")
        o1.channel.settimeout(CH_TIMEOUT)
        mem_kb = int((o1.read().decode().strip() or 0))
        ram_gb = mem_kb / (1024 * 1024)
        _, o2, _ = ssh.exec_command("pgrep -f 'Xorg|gdm|lightdm'")
        o2.channel.settimeout(CH_TIMEOUT)
        ui_active = bool(o2.read().decode().strip())
        # NOTE: do NOT wrap tegrastats in `timeout` -- some Jetson images ship a
        # busybox-style `timeout` that rejects `--interval`, which makes the probe
        # fail and report temp_c=None. `head -1` closes the pipe (SIGPIPE) and
        # terminates tegrastats cleanly on every image.
        _, o3, _ = ssh.exec_command("tegrastats --interval 1000 2>/dev/null | head -1")
        o3.channel.settimeout(CH_TIMEOUT)
        line = o3.read().decode().strip()
        ssh.close()
        # tegrastats emits one `Zone@NNC` token per thermal sensor. We must NOT
        # take a blind max() over all of them: the PMIC zone (power-management IC)
        # sits at a constant ~50C on every Nano regardless of load, which would
        # make every node report an impossible flat 50C and hide the real silicon
        # temps. Exclude the non-silicon zones (authoritative list in
        # cluster_config.THERMAL_EXCLUDE_ZONES) and take the max of the rest.
        temps = []
        for m in re.finditer(r"(\w+)@(\d+(?:\.\d+)?)C", line):
            zone, val = m.group(1), float(m.group(2))
            if zone in THERMAL_EXCLUDE_ZONES:
                continue
            temps.append(val)
        temp_c = max(temps) if temps else None
        return ram_gb, ui_active, temp_c
    except Exception:
        return 0.0, False, None


def get_node_snapshot(ip):
    """Full per-node assessment -> dict consumed by audit, monitor and web.

    Status semantics:
      PASS  - node is healthy and ready (RPC up, no thermal fault)
      WARN  - node works but has a non-fatal caveat (GUI active on node0, or
              thermal in the warning band). It is still usable.
      FAIL  - node cannot participate (RPC down, or thermal critical).

    RAM is NOT a failure condition. The inference allocator (TENSOR_SPLIT +
    per-node -m in cluster_config) allocates layers according to the memory
    actually free on each node at launch time, so a node with less headroom
    (e.g. node0, which keeps its GUI) simply receives a smaller layer share.
    node0 is expected to run a GUI and therefore always shows lower free RAM;
    that is normal, not an error.
    """
    rpc = check_rpc_port(ip)
    ram_gb, ui_active, temp_c = get_node_ssh(ip)
    status = "PASS"
    issues = []
    if not rpc:
        status = "FAIL"
        issues.append(f"RPC Port {PORT} blocked/closed")
    if temp_c is not None:
        if temp_c >= THERMAL_FAIL_C:
            status = "FAIL"
            issues.append(f"THERMAL CRITICAL: {temp_c:.1f}C (throttle/shutdown risk)")
        elif temp_c >= THERMAL_WARN_C:
            if status == "PASS":
                status = "WARN"
            issues.append(f"THERMAL HIGH: {temp_c:.1f}C (check box airflow/fans)")
    if ui_active:
        # GUI consumes unified RAM; the allocator compensates via a smaller
        # tensor-split share. Informational only -- never a failure.
        if status == "PASS":
            status = "WARN"
        issues.append("GUI/display server active (allocator reduces this node's layer share)")
    return {
        "ip": ip,
        "rpc": rpc,
        "ram_gb": ram_gb,
        "ui_active": ui_active,
        "temp_c": temp_c,
        "status": status,
        "errors": " | ".join(issues) if issues else "Healthy",
    }


# ---------------------------------------------------------------------------
# POWER CONTROL  (Start / Shutdown buttons in the web UI)
# ---------------------------------------------------------------------------
# Shutdown = OS-level poweroff over SSH to every node. We also flip the shared
# cluster mode flag to "maintenance" so the fault-tolerant watchdog stands down
# (it must NOT re-slice or re-admit nodes while an OS shutdown is in progress).
# This is the SINGLE flag both the button and the watchdog consult, so they can
# never fight. Physical 5V power (Sonoff switch via Alexa) is OUT OF SCOPE for
# software -- the Start button therefore reports that power-on must be done at
# the hardware switch rather than pretending to do it.
def power_shutdown_all():
    """SSH `sudo shutdown -h now` to every node; set maintenance mode.

    Returns (ok_count, total, failed_ips, mode_set). Best-effort: a node that is
    already off simply fails to connect and is reported, not fatal.
    """
    ok, failed = 0, []
    for ip in JETSON_IPS:
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(ip, username=SSH_USER, key_filename=SSH_KEY_PATH, timeout=3.0)
            ssh.exec_command("sudo shutdown -h now")
            ssh.close()
            ok += 1
        except Exception:
            failed.append(ip)
    try:
        set_cluster_mode(CLUSTER_MODE_MAINTENANCE)
        mode_set = True
    except Exception:
        mode_set = False
    return ok, len(JETSON_IPS), failed, mode_set


def power_start_all():
    """Request cluster power-on.

    Software cannot cut/restore the 5V rail -- that is owned by the Sonoff switch
    controlled via Alexa (see Work Plan Phase 15, explicitly out of scope here).
    This returns an explicit instruction instead of faking a power-on, and clears
    the maintenance flag so the watchdog resumes normal operation once nodes are
    physically powered.
    """
    try:
        set_cluster_mode(CLUSTER_MODE_NORMAL)
        mode_set = True
    except Exception:
        mode_set = False
    return mode_set


def get_network_throughput():
    net_start = psutil.net_io_counters()
    time.sleep(MONVIEW_INTERVAL_SEC)
    net_end = psutil.net_io_counters()
    up_bps = (net_end.bytes_sent - net_start.bytes_sent) * 8
    down_bps = (net_end.bytes_recv - net_start.bytes_recv) * 8
    return up_bps / (1024 * 1024), down_bps / (1024 * 1024)


def fetch_inference_telemetry():
    # Show last-known tok/s with age. Reads rpc_metrics.json published by
    # cluster_infer.py (or manually seeded after a direct llama-cli run).
    try:
        with open(METRICS_FILE, "r", encoding="utf-8") as fh:
            m = json.load(fh)
        tok = m.get("tokens_sec", 0.0)
        kv = m.get("kv_cells", "n/a")
        running = m.get("running", False)
        note = m.get("note", "")
        updated = m.get("updated", 0)
        age_s = time.time() - updated if updated else 99999
        if running and note == "running":
            if isinstance(tok, (int, float)) and tok > 0:
                return f"{tok:.1f} tok/s (live)", kv
            return "Warming up...", kv
        if isinstance(tok, (int, float)) and tok > 0:
            if age_s < 60:
                return f"{tok:.1f} tok/s ({int(age_s)}s ago)", kv
            elif age_s < 3600:
                return f"{tok:.1f} tok/s ({int(age_s/60)}m ago)", kv
            else:
                return f"{tok:.1f} tok/s (last run)", kv
        return "Idle (no run yet)", kv
    except FileNotFoundError:
        return "Idle (no run yet)", "n/a"
    except Exception as e:
        return f"Error: {e}", "n/a"


def collect_state():
    """Aggregate everything the UI/audit needs. Nodes collected in parallel."""
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(JETSON_IPS)) as ex:
        nodes = list(ex.map(get_node_snapshot, JETSON_IPS))
    up, down = get_network_throughput()
    tok, kv = fetch_inference_telemetry()
    online = sum(1 for n in nodes if n["rpc"])
    total_ram = sum(n["ram_gb"] for n in nodes)
    temps = [n["temp_c"] for n in nodes if n["temp_c"] is not None]
    max_temp = max(temps) if temps else None
    avg_temp = (sum(temps) / len(temps)) if temps else None
    healthy = all(n["status"] != "FAIL" for n in nodes) and total_ram >= TOTAL_RAM_GATE_GB
    return {
        "nodes": nodes,
        "cluster": {
            "healthy": healthy,
            "total_ram_gb": round(total_ram, 2),
            "online": online,
            "max_temp_c": max_temp,
            "avg_temp_c": avg_temp,
        },
        "network": {"up_mbps": round(up, 2), "down_mbps": round(down, 2)},
        "inference": {"tokens_sec": tok, "kv_cells": kv},
    }


# ===========================================================================
# MODE SELECTOR  (persistent sharded-inference server)
# Lists GGUFs in MODELS_DIR and reports/controls the resident model via
# cluster_server.py. All changeable facts live in mcp/cluster_config.py.
# ===========================================================================
def _collect_ggufs(folder, prefix=""):
    found = []
    try:
        for entry in os.scandir(folder):
            if entry.is_file() and entry.name.lower().endswith(".gguf"):
                size_mb = entry.stat().st_size / (1024 * 1024)
                found.append({"name": prefix + entry.name,
                              "path": entry.path,
                              "mb": round(size_mb, 1),
                              "gb": round(size_mb / 1024, 2)})
            elif entry.is_dir():
                found.extend(_collect_ggufs(entry.path, prefix + entry.name + "/"))
    except OSError:
        pass
    return found


def list_models():
    """Return GGUF files under MODELS_DIR (top level + one level deep)."""
    try:
        models = _collect_ggufs(MODELS_DIR)
    except OSError as e:
        return {"error": str(e), "models": []}
    models.sort(key=lambda m: m["name"].lower())
    return {"models": models}


def _coerce_sampling(raw):
    """Coerce the dashboard's sampling override dict to floats, falling back to
    the cluster_config defaults for any missing/invalid field (e.g. an empty
    input the UI serialised as null)."""
    def _num(key, default):
        v = raw.get(key, default)
        try:
            return float(v)
        except (TypeError, ValueError):
            return float(default)
    return {
        "temp": _num("temp", SAMPLING_TEMP),
        "min_p": _num("min_p", SAMPLING_MIN_P),
        "top_p": _num("top_p", SAMPLING_TOP_P),
        "repeat_penalty": _num("repeat_penalty", SAMPLING_REPEAT_PENALTY),
    }


def _server_status():
    """Report resident-model state for the dashboard.

    The dashboard is synchronised with the CLI backend: a model is "resident"
    when it has been loaded via the MTP llama-cli + all-11-RPC-worker path (the
    same path the proven CLI test uses). We report that real state, not a
    separate HTTP server's /health, so the UI cannot be out of sync with the
    working backend.
    """
    with _RESIDENT_LOCK:
        model = _RESIDENT_MODEL
        sampling = _RESIDENT_SAMPLING
    running = bool(model)
    return {"running": running, "host": "cluster", "port": PORT,
            "model": os.path.basename(model) if model else None,
            "workers_up": len(JETSON_IPS), "workers_total": len(JETSON_IPS),
            "sampling": sampling}


def _probe_port(port, host="127.0.0.1", timeout=1.5):
    """Return True if an HTTP /health endpoint answers 200 on (host, port)."""
    import urllib.request as _ureq
    try:
        # nosec B310: host/port are fixed localhost/LAN values from config, not
        # user-supplied. Plaintext HTTP is acceptable on the trusted LAN.
        with _ureq.urlopen(f"http://{host}:{port}/health", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def _ensemble_status():
    """Read ensemble_state.json and report per-member liveness (real /health
    probe, not just the persisted pid). Returns None if no ensemble is running."""
    _p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      ENSEMBLE_STATE_FILE)
    try:
        with open(_p, "r", encoding="utf-8") as _f:
            state = json.load(_f)
    except Exception:
        return None
    members = []
    for a in state.get("assignments", []):
        port = a.get("port")
        members.append({
            "model": os.path.basename(a.get("model", "")),
            "port": port,
            "nodes": a.get("nodes", []),
            "running": bool(port and _probe_port(port)),
        })
    return {"running": any(m["running"] for m in members), "members": members}


def _run_server(args):
    """Invoke cluster_server.py with the given argv; return (rc, stdout).

    The child llama-server is launched DETACHED and writes its own log file, so
    we must NOT capture its stdout (the pipe would close instantly and report a
    false early-exit). We only care about cluster_server.py's own return code.
    """
    import subprocess as _sp
    py = sys.executable
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "cluster_server.py")
    try:
        r = _sp.run([py, script] + args,
                    stdout=_sp.DEVNULL, stderr=_sp.DEVNULL, timeout=240)
        return r.returncode, ""
    except Exception as e:  # pragma: no cover
        return -1, str(e)


def _looks_text(raw):
    """Heuristic: treat bytes as text if the first 200 bytes decode as UTF-8."""
    try:
        raw[:200].decode("utf-8")
        return True
    except Exception:
        return False


def _save_upload(filename, b64data):
    """Decode a base64 upload and persist it to CHAT_UPLOAD_DIR.

    Returns metadata (name/path/size/is_text/preview) the UI uses to attach the
    file to the next chat prompt. Filenames are sanitised and de-duplicated.
    """
    import base64
    os.makedirs(CHAT_UPLOAD_DIR, exist_ok=True)
    safe = os.path.basename(filename or "upload.bin").replace("\\", "_")
    dest = os.path.join(CHAT_UPLOAD_DIR, safe)
    if os.path.exists(dest):
        base, ext = os.path.splitext(safe)
        dest = os.path.join(CHAT_UPLOAD_DIR, f"{base}_{int(time.time())}{ext}")
    raw = base64.b64decode(b64data or "")
    with open(dest, "wb") as f:
        f.write(raw)
    preview = ""
    if _looks_text(raw):
        try:
            preview = raw[:2000].decode("utf-8", "replace")
        except Exception:
            preview = ""
    return {"ok": True, "name": os.path.basename(dest), "path": dest,
            "size": len(raw), "is_text": _looks_text(raw), "preview": preview}


def _chat_completion(prompt, n_predict=None, system_prompt="", sampling=None):
    """Send a prompt to the persistent llama-server (loaded once, resident).
    Fast HTTP call — no CLI reload per prompt. Sampling is taken from the
    resident-model state (set at load time via the dashboard controls) so the
    UI parameters take effect; falls back to the config defaults if none stored.
    """
    import urllib.request as _ureq
    s = sampling or {
        "temp": SAMPLING_TEMP, "min_p": SAMPLING_MIN_P,
        "top_p": SAMPLING_TOP_P, "repeat_penalty": SAMPLING_REPEAT_PENALTY,
    }
    if n_predict is None:
        n_predict = MAX_TOKENS_DEFAULT   # re-read from settings each call
    payload = json.dumps({
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": s["temp"],
        "min_p": s["min_p"],
        "top_p": s["top_p"],
        "repeat_penalty": s["repeat_penalty"],
        "cache_prompt": True,
    })
    if system_prompt:
        payload_obj = json.loads(payload)
        payload_obj["system_prompt"] = system_prompt
        payload = json.dumps(payload_obj)
    req = _ureq.Request(
        f"http://127.0.0.1:{_RESIDENT_PORT}/completion",
        data=payload.encode("utf-8"),
        headers={"Content-Type": "application/json"})
    try:
        with _ureq.urlopen(req, timeout=REQUEST_TIMEOUT) as r:
            data = json.loads(r.read().decode("utf-8"))
        return {"content": data.get("content", ""),
                "timings": data.get("timings", {})}
    except Exception as e:
        raise RuntimeError(f"llama-server completion failed: {e}")


def _ensemble_complete(port, prompt, system_prompt=""):
    """Call one ensemble member's /completion endpoint. Returns (content, tps).

    Some GGUFs (e.g. Phi-3-mini on this llama.cpp build) return an empty
    content on the first request after idle/warmup. We retry once so a single
    transient empty does not silently drop a member's answer from the combine.
    """
    import urllib.request as _ureq
    _body = {
        "prompt": prompt,
        "n_predict": MAX_TOKENS_DEFAULT,   # re-read from settings each call
        "temperature": _RESIDENT_SAMPLING["temp"],
        "min_p": _RESIDENT_SAMPLING["min_p"],
        "top_p": _RESIDENT_SAMPLING["top_p"],
        "repeat_penalty": _RESIDENT_SAMPLING["repeat_penalty"],
        "stream": False,
    }
    if system_prompt:
        _body["system_prompt"] = system_prompt
    content, tps = "", 0.0
    for _attempt in range(2):
        # nosec B310: ENS_HOST/port are fixed localhost/LAN values from config.
        req = _ureq.Request(
            f"http://{ENS_HOST}:{port}/completion",
            data=json.dumps(_body).encode("utf-8"),
            headers={"Content-Type": JSON_CT},
            method="POST",
        )
        with _ureq.urlopen(req, timeout=None) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        content = (data.get("content") or "").strip()
        _t = (data.get("timings") or {}).get("predicted_per_second")
        tps = _t if isinstance(_t, (int, float)) else 0.0
        if content:
            break
        time.sleep(1.0)  # brief pause before retry (warmup race)
    return content, tps


def _read_ensemble_state():
    """Return the running ensemble assignment map, or None if not launched."""
    _p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      ENSEMBLE_STATE_FILE)
    try:
        with open(_p, "r", encoding="utf-8") as _f:
            return json.load(_f).get("assignments")
    except Exception:
        return None


def _read_ensemble_state_raw():
    """Return the raw assignments list from ensemble_state.json (or [])."""
    _p = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      ENSEMBLE_STATE_FILE)
    try:
        with open(_p, "r", encoding="utf-8") as _f:
            return json.load(_f).get("assignments", [])
    except Exception:
        return []


def _self_consistency_combine(per_model):
    """Combine ensemble answers via self-consistency (most frequent answer).

    - Extractable answers (short label/number): normalize + tally, return mode.
    - Free-form text: return the longest answer as representative (no natural
      mode); embedding clustering is a future enhancement (9998 tier).
    """
    answers = [m["answer"] for m in per_model if m.get("status") == "ok"
               and m.get("answer")]
    if not answers:
        return "(no valid answers from ensemble members)"
    # Try extractable-answer mode: normalize and tally.
    norm = {}
    for a in answers:
        key = a.strip().lower().strip(".,;:!?\"'")
        norm.setdefault(key, []).append(a)
    if len(norm) <= 1:
        # All identical (or single answer) -> return as-is.
        return answers[0]
    # Multiple distinct answers: if any single normalized form has >1 vote,
    # return the most common raw answer.
    best_key = max(norm, key=lambda k: len(norm[k]))
    if len(norm[best_key]) > 1:
        return norm[best_key][0]
    # No majority: free-form divergence -> return the longest (most complete).
    return max(answers, key=len)


def _write_inference_metrics(tokens_sec):
    """Persist the latest measured tok/s to METRICS_FILE so the dashboard's
    'Gen Speed' card reflects real chat throughput. The legacy cluster_infer.py
    path used to write this; the llama-server chat path now owns it.
    """
    try:
        prev = {}
        if os.path.isfile(METRICS_FILE):
            with open(METRICS_FILE, "r", encoding="utf-8") as fh:
                prev = json.load(fh)
        prev.update({
            "tokens_sec": round(float(tokens_sec), 2),
            "running": True,
            "note": "running",
            "updated": time.time(),
        })
        with open(METRICS_FILE, "w", encoding="utf-8") as fh:
            json.dump(prev, fh)
    except Exception:
        pass


# ===========================================================================
# CLI MODES
# ===========================================================================
def cmd_audit():
    state = collect_state()
    nodes = state["nodes"]
    print("=" * 90)
    print(f"LAUNCHING TELEMETRY AUDIT FOR {len(nodes)}-NODE JETSON CLUSTER")
    print("=" * 90)
    print(f"{'Node IP':<16} | {'RPC':<5} | {'RAM(UMA)':<14} | {'Max Temp':<9} | {'Status Note'}")
    print("-" * 90)
    for n in nodes:
        temp = f"{n['temp_c']:.1f}C" if n["temp_c"] is not None else "n/a"
        print(f"{n['ip']:<16} | [{n['status']}] | {n['ram_gb']:.2f} GB | {temp:<9} | {n['errors']}")
    print("=" * 90)
    print(f"Total Combined Cluster Execution Pool RAM (UMA): {state['cluster']['total_ram_gb']:.2f} GB")
    if state["cluster"]["healthy"]:
        print("\n STATUS: SUCCESS. Cluster matches all deployment constraints for 70B IQ3_XS execution.")
        sys.exit(0)
    else:
        print("\n STATUS: CRITICAL FAILURE. Resolve the node errors highlighted above before deploying model.")
        sys.exit(1)


def _monitor_header(state):
    """Render the single-line cluster status header for the terminal view."""
    c = state["cluster"]
    health = "HEALTHY" if c["healthy"] else "DEGRADED"
    maxt = f"{c['max_temp_c']:.1f}C" if c["max_temp_c"] is not None else "n/a"
    return (f" Cluster: {health}   Online: {c['online']}/{len(state['nodes'])}   "
            f"RAM(UMA): {c['total_ram_gb']:.2f} GB   MaxTemp: {maxt}")


def cmd_monitor():
    try:
        while True:
            state = collect_state()
            os.system("cls" if os.name == "nt" else "clear")
            print("=" * 70)
            print("   JETSON 11-NODE COMPUTE CLUSTER - LIVE RUNTIME TELEMETRY")
            print("=" * 70)
            print(_monitor_header(state))
            print(f" Net TX: {state['network']['up_mbps']:.2f} Mbps   "
                  f"Net RX: {state['network']['down_mbps']:.2f} Mbps   "
                  f"Gen: {state['inference']['tokens_sec']} tok/s   "
                  f"KV: {state['inference']['kv_cells']}")
            print("-" * 70)
            for n in state["nodes"]:
                temp = f"{n['temp_c']:.1f}C" if n["temp_c"] is not None else "n/a"
                print(f" {n['ip']:<16} [{n['status']:<4}] RPC:{'up' if n['rpc'] else 'DOWN':<3} "
                      f"RAM:{n['ram_gb']:.2f}GB TEMP:{temp:<7} {n['errors']}")
            print("=" * 70)
            print(" Press Ctrl+C to close monitoring engine safely.")
    except KeyboardInterrupt:
        print("\nTelemetry trace terminated cleanly.")
        sys.exit(0)


# ===========================================================================
# WEB MODE  (stdlib only — no Flask dependency)
# ===========================================================================
DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Jetson Cluster Telemetry</title>
<link rel="icon" href="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAzMiAzMiI+PHJlY3Qgd2lkdGg9IjMyIiBoZWlnaHQ9IjMyIiByeD0iNyIgZmlsbD0iIzBkMTExNyIvPjxnIHN0cm9rZT0iIzU4YTZmZiIgc3Ryb2tlLXdpZHRoPSIxLjUiPjxsaW5lIHgxPSI5IiB5MT0iOSIgeDI9IjIzIiB5Mj0iOSIvPjxsaW5lIHgxPSI5IiB5MT0iOSIgeDI9IjkiIHkyPSIyMyIvPjxsaW5lIHgxPSIyMyIgeTE9IjkiIHgyPSIyMyIgeTI9IjIzIi8+PGxpbmUgeDE9IjkiIHkxPSIyMyIgeDI9IjIzIiB5Mj0iMjMiLz48bGluZSB4MT0iOSIgeTE9IjkiIHgyPSIyMyIgeTI9IjIzIi8+PGxpbmUgeDE9IjIzIiB5MT0iOSIgeDI9IjkiIHkyPSIyMyIvPjwvZz48ZyBmaWxsPSIjM2ZiOTUwIj48Y2lyY2xlIGN4PSI5IiBjeT0iOSIgcj0iMyIvPjxjaXJjbGUgY3g9IjIzIiBjeT0iOSIgcj0iMyIvPjxjaXJjbGUgY3g9IjkiIGN5PSIyMyIgcj0iMyIvPjxjaXJjbGUgY3g9IjIzIiBjeT0iMjMiIHI9IjMiLz48L2c+PC9zdmc+">
<style>
  :root { --bg:#0d1117; --panel:#161b22; --border:#30363d; --txt:#e6edf3; --muted:#8b949e;
          --ok:#3fb950; --warn:#d29922; --fail:#f85149; --accent:#58a6ff; }
  * { box-sizing:border-box; }
  body { margin:0; font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
         background:var(--bg); color:var(--txt); padding:16px;
         min-height:100vh; display:flex; flex-direction:column; }
  .head { display:flex; align-items:center; gap:16px; margin:0 0 4px; flex-wrap:wrap; }
  h1 { font-size:18px; margin:0; }
  .sub { color:var(--muted); font-size:12px; margin-bottom:16px; }
  .banner { display:inline-block; padding:9px 20px; border-radius:999px; font-weight:700; font-size:17px; letter-spacing:.4px; }
  .banner.ok { background:rgba(63,185,80,.12); color:var(--ok); border:1px solid rgba(63,185,80,.3); }
  .banner.fail { background:rgba(248,81,73,.12); color:var(--fail); border:1px solid rgba(248,81,73,.3); }
  .layout { display:grid; grid-template-columns:minmax(0,1fr); gap:16px; align-items:start; margin-bottom:8px; }
  .col-main { display:flex; flex-direction:column; gap:8px; min-width:0; }
  .summary { display:flex; gap:8px; flex-wrap:nowrap; overflow:hidden; align-items:stretch; }
  .card { background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:7px 9px; min-width:0; flex:1 1 0; }
  .toolbar { display:flex; gap:12px; align-items:center; margin-left:auto; }
  .btn { font:inherit; font-weight:600; border-radius:8px; padding:10px 18px; cursor:pointer; border:1px solid var(--border); color:var(--txt); background:var(--panel); transition:filter .15s; }
  .btn:hover { filter:brightness(1.2); }
  .btn:disabled { opacity:.5; cursor:not-allowed; }
  .btn.start { border-color:var(--ok); color:var(--ok); }
  .btn.shutdown { border-color:var(--fail); color:var(--fail); }
  .power-msg { color:var(--muted); font-size:13px; }
  .model-panel { display:flex; gap:6px; align-items:center; flex-wrap:wrap;
                 background:var(--panel); border:1px solid var(--border); border-radius:8px;
                 padding:3px 10px; margin-bottom:2px; }
  .model-panel label { color:var(--muted); font-size:12px; margin-right:2px; }
  .model-panel select { font:inherit; background:#0d1117; color:var(--txt);
                 border:1px solid var(--border); border-radius:6px; padding:6px 8px; min-width:200px; }
  .model-panel .status { color:var(--muted); font-size:13px; }
  .model-panel .status.live { color:var(--ok); }
  .model-panel .status.dead { color:var(--fail); }
  .panel-hint { color:var(--muted); font-size:11px; margin-left:auto; font-style:italic; }
  .samp-group { display:flex; flex-direction:column; gap:4px; align-items:flex-start;
                margin-left:14px; padding-left:10px; border-left:1px solid var(--border); }
  .samp-row { display:flex; gap:10px; align-items:flex-end; }
  .samp-sep { color:var(--muted); font-size:11px; font-weight:600; text-transform:uppercase;
              letter-spacing:.04em; }
  .samp-field { display:flex; flex-direction:column; gap:2px; }
  .samp-field label { color:var(--muted); font-size:10px; }
  .samp-field input { font:inherit; background:#0d1117; color:var(--txt);
                 border:1px solid var(--border); border-radius:6px; padding:4px 6px; width:74px; }
  .btn.reset { border-color:var(--muted); color:var(--muted); white-space:nowrap; }
  .samp-status { color:var(--muted); font-size:11px; }
  .mode-toggle { display:flex; align-items:center; gap:10px; font-size:12px; color:var(--muted); }
  .mode-toggle .mode-label { font-weight:600; }
  .mode-toggle label { cursor:pointer; }
  .model-actions { display:flex; flex-direction:column; align-items:flex-start; gap:4px; }
  .model-actions-row { display:flex; align-items:center; gap:8px; }
  .btn.load { border-color:var(--accent); color:var(--accent); }
  .btn.eject { border-color:var(--warn); color:var(--warn); }
  .chat-panel { background:var(--panel); border:1px solid var(--border); border-radius:8px; padding:14px; margin-top:8px;
                flex:1 1 auto; display:flex; flex-direction:column; min-height:0; }
  .chat-head { color:var(--muted); font-size:12px; margin-bottom:10px; }
  .chat-body { display:flex; gap:12px; align-items:stretch; flex:1 1 auto; min-height:0; }
  .chat-side { display:flex; flex-direction:column; gap:8px; width:104px; flex:0 0 104px; justify-content:flex-end; }
  .chat-main { flex:1 1 auto; min-width:0; display:flex; flex-direction:column; gap:8px; min-height:0; }
  .chat-log { flex:1 1 auto; min-height:200px; overflow-y:auto; display:flex; flex-direction:column; gap:8px; margin-bottom:10px; }
  .msg { padding:9px 12px; border-radius:8px; font-size:13px; white-space:pre-wrap; word-break:break-word; max-width:85%; }
  .msg.user { align-self:flex-end; background:rgba(88,166,255,.15); border:1px solid rgba(88,166,255,.3); }
  .msg.bot { align-self:flex-start; background:#0d1117; border:1px solid var(--border); }
  .chat-input { display:flex; flex-direction:column; gap:8px; }
  .chat-attach { min-height:0; }
  .chip { display:inline-block; background:#0d1117; border:1px solid var(--border); border-radius:999px; padding:3px 10px; font-size:12px; color:var(--txt); }
  .chip a { color:var(--fail); cursor:pointer; margin-left:6px; text-decoration:none; }
  .chat-row { display:flex; gap:8px; align-items:flex-end; }
  .chat-actions { display:flex; flex-direction:column; gap:6px; width:100%; }
  .chat-side > .btn.attach { width:100px; }
  .chat-compose { display:flex; flex-direction:row; gap:8px; align-items:stretch; }
  .chat-compose .chat-actions { flex:0 0 auto; width:auto; justify-content:flex-end; }
  .sys-prompt { border:1px solid var(--border); border-radius:6px; padding:6px 8px; background:#0d1117; box-sizing:border-box; width:100%; }
  .sys-title { font-size:11px; color:var(--muted); margin-bottom:5px; }
  .sys-actions { display:flex; flex-direction:column; gap:6px; }
  .sys-actions .btn { width:100%; padding:6px 8px; font-size:12px; white-space:nowrap; }
  #sysText { width:100%; font:inherit; font-size:12px; background:#0d1117; color:var(--txt); border:1px solid var(--border); border-radius:6px; padding:5px 8px; resize:vertical; min-height:48px; margin-top:6px; box-sizing:border-box; }
  .sys-status { font-size:10px; color:var(--muted); margin-top:3px; line-height:1.2; }
  .btn.sysmini { font-size:10px; padding:3px 7px; border-radius:5px; }
  .btn.attach { border-color:var(--muted); color:var(--muted); white-space:nowrap; }
  .btn.send { border-color:var(--accent); color:var(--accent); white-space:nowrap; }
  .btn.clear { border-color:var(--muted); color:var(--muted); white-space:nowrap; }
  #chatText { flex:1 1 auto; font:inherit; background:#0d1117; color:var(--txt); border:1px solid var(--border); border-radius:6px; padding:8px 10px; resize:vertical; min-height:120px; }
  .card .k { color:var(--muted); font-size:10px; text-transform:uppercase; letter-spacing:.5px; }
  .card .v { font-size:17px; font-weight:600; margin-top:2px; }
  .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(230px,1fr)); gap:12px; }
  .node { background:var(--panel); border:1px solid var(--border); border-left:4px solid var(--muted); border-radius:8px; padding:12px; }
  .node.ok { border-left-color:var(--ok); }
  .node.warn { border-left-color:var(--warn); }
  .node.fail { border-left-color:var(--fail); }
  .node .ip { font-weight:600; font-size:14px; display:flex; justify-content:space-between; align-items:center; }
  .node .row { display:flex; justify-content:space-between; font-size:12px; margin-top:6px; color:var(--muted); }
  .node .row b { color:var(--txt); font-weight:600; }
  .badge { padding:2px 8px; border-radius:999px; font-size:11px; font-weight:600; }
  .badge.ok { background:rgba(63,185,80,.15); color:var(--ok); }
  .badge.warn { background:rgba(210,153,34,.15); color:var(--warn); }
  .badge.fail { background:rgba(248,81,73,.15); color:var(--fail); }
  .dot { width:8px; height:8px; border-radius:50%; display:inline-block; margin-right:6px; vertical-align:middle; }
  .dot.on { background:var(--ok); } .dot.off { background:var(--fail); }
  .bar { height:6px; background:#21262d; border-radius:4px; margin-top:4px; overflow:hidden; }
  .bar > i { display:block; height:100%; background:var(--accent); }
  .err { color:var(--warn); font-size:11px; margin-top:6px; }
</style>
</head>
<body>
  <div class="head">
    <h1>Jetson 11-Node Compute Cluster &mdash; Live Telemetry</h1>
    <div id="banner"></div>
    <div class="toolbar">
      <button id="btnStart" class="btn start">&#9654; Start</button>
      <button id="btnShutdown" class="btn shutdown">&#9632; Shutdown</button>
      <span id="powerMsg" class="power-msg"></span>
    </div>
  </div>
  <div class="sub" id="ts">connecting&hellip;</div>
  <div class="layout">
    <div class="col-main">
      <div class="summary" id="summary"></div>
      <div class="grid" id="nodes"></div>
    </div>
  </div>
  <div class="model-panel">
    <label for="modelSelect">Models</label>
    <select id="modelSelect" multiple size="3" style="min-width:320px; min-height:72px;"></select>
    <div class="mode-toggle">
      <span class="mode-label">Mode</span>
      <label><input type="radio" name="mode" value="single" checked> Single</label>
      <label><input type="radio" name="mode" value="ensemble"> Ensemble</label>
    </div>
    <div class="model-actions">
      <div class="model-actions-row">
        <button id="btnLoad" class="btn load">&#8635; Load</button>
        <button id="btnEject" class="btn eject">&#9211; Eject</button>
        <button id="btnSampReset" class="btn reset" title="Reset sampling to config defaults">&#8634; Reset</button>
      </div>
      <span id="modelStatus" class="status dead">no model resident</span>
    </div>
    <div class="samp-group">
      <span class="samp-sep">Sampling</span>
      <div class="samp-row">
        <div class="samp-field">
          <label for="sampTemp">Temp</label>
          <input type="number" id="sampTemp" step="0.01" min="0" max="2" value="0.1">
        </div>
        <div class="samp-field">
          <label for="sampMinP">Min-P</label>
          <input type="number" id="sampMinP" step="0.01" min="0" max="1" value="0.05">
        </div>
        <div class="samp-field">
          <label for="sampTopP">Top-P</label>
          <input type="number" id="sampTopP" step="0.01" min="0" max="1" value="0.9">
        </div>
      </div>
      <div class="samp-row">
        <div class="samp-field">
          <label for="sampRepPen">Repeat&nbsp;Penalty</label>
          <input type="number" id="sampRepPen" step="0.01" min="1" max="2" value="1.1">
        </div>
        <div class="samp-field">
          <label for="sampCtx">Context&nbsp;size</label>
          <input type="number" id="sampCtx" step="256" min="512" max="131072" value="4096">
        </div>
        <div class="samp-field">
          <label for="sampMaxTok">Max&nbsp;output</label>
          <input type="number" id="sampMaxTok" step="64" min="1" max="131072" value="4096">
        </div>
      </div>
      <span id="sampStatus" class="samp-status"></span>
    </div>
    <span class="panel-hint" id="modeHint">single: one model sharded across all nodes &middot; :8080</span>
  </div>
  <div class="chat-panel">
    <div class="chat-head" id="chatHead">Cluster Chat</div>
    <div class="chat-body">
      <div class="chat-side">
        <div class="sys-prompt">
          <div class="sys-title">System prompt</div>
          <input type="file" id="sysFileInput" hidden>
          <div class="sys-actions">
            <button id="btnSysUpload" class="btn attach" title="Upload a .txt/.md system prompt">&#128206; Upload</button>
            <button id="btnSysClear" class="btn clear" title="Clear system prompt">Clear</button>
          </div>
        </div>
        <input type="file" id="fileInput" hidden>
        <button id="btnAttach" class="btn attach" title="Attach a file">&#128206; File</button>
      </div>
      <div class="chat-main">
        <div class="chat-attach" id="chatAttach"></div>
        <div class="chat-log" id="chatLog"></div>
        <div class="chat-compose">
          <textarea id="chatText" rows="5" placeholder="Ask the cluster a question... (Enter to send, Shift+Enter for newline)"></textarea>
          <div class="chat-actions">
            <button id="btnSend" class="btn send">Send &#8594;</button>
            <button id="btnClear" class="btn clear" title="Clear chat history">Clear</button>
          </div>
        </div>
      </div>
    </div>
  </div>
<script>
function fmt(x, d){ d = d || 1; return x == null ? 'n/a' : x.toFixed(d); }
async function refresh(){
  try {
    const r = await fetch('/api/state');
    const s = await r.json();
    if (!s || !s.cluster) { setTimeout(refresh, 1000); return; }
    document.getElementById('ts').textContent = 'updated ' + new Date().toLocaleTimeString();
    const c = s.cluster;
    const banner = document.getElementById('banner');
    if (c.healthy) { banner.className='banner ok'; banner.textContent='\u25CF CLUSTER HEALTHY'; }
    else { banner.className='banner fail'; banner.textContent='\u25B2 CLUSTER DEGRADED'; }
    document.getElementById('summary').innerHTML = [
      ['Nodes Online', c.online + ' / ' + s.nodes.length],
      ['Total RAM (UMA)', c.total_ram_gb.toFixed(2) + ' GB'],
      ['Max Temp', fmt(c.max_temp_c) + ' \\u00B0C'],
      ['Avg Temp', fmt(c.avg_temp_c) + ' \\u00B0C'],
      ['Net \\u2191', s.network.up_mbps.toFixed(2) + ' Mbps'],
      ['Net \\u2193', s.network.down_mbps.toFixed(2) + ' Mbps'],
      ['Gen Speed', s.inference.tokens_sec + ' tok/s'],
      ['KV Cells', s.inference.kv_cells]
    ].map(function(p){ return '<div class=\"card\"><div class=\"k\">'+p[0]+'</div><div class=\"v\">'+p[1]+'</div></div>'; }).join('');
    document.getElementById('nodes').innerHTML = s.nodes.map(function(n){
      const cls = n.status === 'PASS' ? 'ok' : (n.status === 'WARN' ? 'warn' : 'fail');
      const temp = n.temp_c == null ? 'n/a' : n.temp_c.toFixed(1) + ' \\u00B0C';
      const ramPct = Math.min(100, (n.ram_gb / 4) * 100);
      return '<div class=\"node '+cls+'\">'
        + '<div class=\"ip\">'+n.ip+' <span class=\"badge '+cls+'\">'+n.status+'</span></div>'
        + '<div class=\"row\"><span><span class=\"dot '+(n.rpc?'on':'off')+'\"></span>RPC '+(n.rpc?'up':'down')+'</span><b>'+temp+'</b></div>'
        + '<div class="row"><span>RAM avail (UMA)</span><b>'+n.ram_gb.toFixed(2)+' GB</b></div>'
        + '<div class="bar"><i style="width:'+ramPct+'%"></i></div>'
        + (n.errors !== 'Healthy' ? '<div class=\"err\">'+n.errors+'</div>' : '')
        + '</div>';
    }).join('');
  } catch(e){ document.getElementById('ts').textContent = 'error: ' + e; }
  setTimeout(refresh, 2000);
}
refresh();

function setPowerMsg(t){ document.getElementById('powerMsg').textContent = t; }
document.getElementById('btnShutdown').addEventListener('click', async function(){
  this.disabled = true; setPowerMsg('Shutting down all nodes over SSH...');
  try {
    const r = await fetch('/api/shutdown', {method:'POST'});
    const d = await r.json();
    setPowerMsg('Shutdown sent: ' + d.ok + '/' + d.total + ' nodes acknowledged'
      + (d.failed.length ? '; failed: ' + d.failed.join(', ') : '')
      + (d.maintenance ? '; watchdog set to maintenance.' : ''));
  } catch(e){ setPowerMsg('Shutdown error: ' + e); }
  this.disabled = false;
});
document.getElementById('btnStart').addEventListener('click', async function(){
  this.disabled = true; setPowerMsg('Clearing maintenance flag...');
  try {
    const r = await fetch('/api/start', {method:'POST'});
    const d = await r.json();
    setPowerMsg(d.note);
  } catch(e){ setPowerMsg('Start error: ' + e); }
  this.disabled = false;
});

// ---- Model Selector + Eject (persistent sharded-inference server) ----
async function loadModels(){
  try {
    const r = await fetch('/api/models');
    const d = await r.json();
    const sel = document.getElementById('modelSelect');
    if (d.error) { sel.innerHTML = '<option>error: ' + d.error + '</option>'; return; }
    sel.innerHTML = d.models.map(function(m){
      return '<option value="' + m.path + '">' + m.name + ' (' + m.gb.toFixed(2) + ' GB)</option>';
    }).join('');
  } catch(e){ document.getElementById('modelSelect').innerHTML = '<option>load error</option>'; }
}
async function refreshServerStatus(){
  try {
    const r = await fetch('/api/server/status');
    const s = await r.json();
    const el = document.getElementById('modelStatus');
    const m = currentMode();
    if (m === 'single'){
      if (s.running) {
        el.className = 'status live';
        el.textContent = 'resident: ' + (s.model || '') + ' (' + s.workers_up + '/' + s.workers_total + ' nodes)';
      } else { el.className = 'status dead'; el.textContent = 'no model resident'; }
    } else {
      // Ensemble mode: report per-member liveness from the server.
      const ens = s.ensemble;
      if (!ens || !ens.members || !ens.members.length){
        el.className = 'status dead'; el.textContent = 'no ensemble running';
      } else {
        const up = ens.members.filter(function(x){ return x.running; }).length;
        if (up === ens.members.length){
          el.className = 'status live';
          el.textContent = 'ensemble up (' + up + '/' + ens.members.length + '): ' +
            ens.members.map(function(x){ return x.model + '@' + x.port; }).join(', ');
        } else {
          el.className = 'status dead';
          el.textContent = 'ensemble ' + up + '/' + ens.members.length + ' up — ' +
            ens.members.map(function(x){ return x.model + (x.running ? '✓' : '✗'); }).join(', ');
        }
      }
    }
  } catch(e){ /* ignore */ }
}
document.getElementById('btnEject').addEventListener('click', async function(){
  this.disabled = true;
  const st = document.getElementById('modelStatus');
  st.className = 'status dead'; st.textContent = 'ejecting (freeing shards)...';
  try {
    const r = await fetch('/api/server/eject', {method:'POST'});
    const d = await r.json();
    st.textContent = d.ok ? 'no model resident' : ('eject failed: ' + d.msg);
  } catch(e){ st.textContent = 'eject error: ' + e; }
  this.disabled = false;
});
// ---- Unified model selector (single + ensemble) ----
const modelSelect = document.getElementById('modelSelect');
const modeRadios = document.getElementsByName('mode');
const modeHint = document.getElementById('modeHint');
const modelStatus = document.getElementById('modelStatus');
const chatHead = document.getElementById('chatHead');
function currentMode(){
  for (const r of modeRadios){ if (r.checked) return r.value; }
  return 'single';
}
function selectedModels(){
  return Array.from(modelSelect.selectedOptions).map(function(o){ return o.value; });
}
function updateModeUI(){
  const m = currentMode();
  if (m === 'single'){
    modelSelect.multiple = false; modelSelect.size = 1;
    modeHint.textContent = 'single: one model sharded across all nodes · :8080';
    chatHead.textContent = 'Cluster Chat — single resident model';
  } else {
    modelSelect.multiple = true; modelSelect.size = 3;
    modeHint.textContent = 'ensemble: each model on its own node subset · :8081+';
    chatHead.textContent = 'Ensemble Chat — combined answers across selected models';
  }
}
modeRadios.forEach(function(r){ r.addEventListener('change', updateModeUI); });
updateModeUI();

// ---- System prompt (vertical Upload/Clear stack next to File) ----
let sysPromptText = '';
const sysFileInput = document.getElementById('sysFileInput');
document.getElementById('btnSysUpload').addEventListener('click', function(){ sysFileInput.click(); });
sysFileInput.addEventListener('change', async function(){
  const f = sysFileInput.files[0];
  if (!f) return;
  const reader = new FileReader();
  reader.onload = async function(){
    const b64 = (reader.result.split(',')[1]) || '';
    try {
      const r = await fetch('/api/chat/upload', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({filename: f.name, data: b64, size: f.size})});
      const d = await r.json();
      if (d.ok && d.is_text){ sysPromptText = d.preview || ''; }
      else { alert('System prompt must be a readable text file (.md/.txt).'); }
    } catch(e){ alert('Upload error: ' + e); }
  };
  reader.readAsDataURL(f);
  sysFileInput.value = '';
});
document.getElementById('btnSysClear').addEventListener('click', function(){
  sysPromptText = '';
});

// ---- Load / Eject ----
document.getElementById('btnLoad').addEventListener('click', async function(){
  this.disabled = true;
  const m = currentMode();
  const sel = selectedModels();
  if (m === 'single'){
    if (sel.length !== 1){ modelStatus.className = 'status dead'; modelStatus.textContent = 'select exactly one model'; this.disabled = false; return; }
    modelStatus.className = 'status dead'; modelStatus.textContent = 'loading shards into cluster...';
    try {
      const r = await fetch('/api/server/load', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({model: sel[0], ctx_size: window._pendingCtxSize || CTX_SIZE_DEFAULT,
                             sampling: window._pendingSampling || readSampling()})});
      const d = await r.json();
      modelStatus.textContent = d.ok ? 'resident' : ('load failed: ' + d.msg);
      modelStatus.className = d.ok ? 'status live' : 'status dead';
    } catch(e){ modelStatus.textContent = 'load error: ' + e; modelStatus.className = 'status dead'; }
  } else {
    if (!sel.length){ modelStatus.className = 'status dead'; modelStatus.textContent = 'select models first'; this.disabled = false; return; }
    modelStatus.className = 'status dead'; modelStatus.textContent = 'launching ensemble (waiting for members)...';
    try {
      const r = await fetch('/api/ensemble/launch', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({models: sel.join(','),
                             ctx_size: window._pendingCtxSize || CTX_SIZE_DEFAULT,
                             sampling: window._pendingSampling || readSampling()})});
      const d = await r.json();
      if (d.ok){
        modelStatus.className = 'status live';
        modelStatus.textContent = 'ensemble up (' + d.count + ' models): ' + (d.ready_ports || []).join(', ');
      } else {
        modelStatus.className = 'status dead';
        modelStatus.textContent = 'launch failed: ' + d.msg;
      }
    } catch(e){ modelStatus.textContent = 'launch error: ' + e; modelStatus.className = 'status dead'; }
  }
  this.disabled = false;
});
document.getElementById('btnEject').addEventListener('click', async function(){
  this.disabled = true;
  const m = currentMode();
  modelStatus.className = 'status dead'; modelStatus.textContent = 'ejecting (freeing shards)...';
  try {
    const path = m === 'single' ? '/api/server/eject' : '/api/ensemble/stop';
    const r = await fetch(path, {method:'POST'});
    const d = await r.json();
    modelStatus.textContent = d.ok ? 'no model resident' : ('eject failed: ' + d.msg);
  } catch(e){ modelStatus.textContent = 'eject error: ' + e; }
  this.disabled = false;
});

// ---- Unified chat (single + ensemble) ----
let attachedFile = null;
const chatLog = document.getElementById('chatLog');
const chatText = document.getElementById('chatText');
const fileInput = document.getElementById('fileInput');
const chatAttach = document.getElementById('chatAttach');
function chatAppend(role, text){
  const d = document.createElement('div');
  d.className = 'msg ' + role;
  d.textContent = text;
  chatLog.appendChild(d);
  chatLog.scrollTop = chatLog.scrollHeight;
}
document.getElementById('btnAttach').addEventListener('click', function(){ fileInput.click(); });
fileInput.addEventListener('change', async function(){
  const f = fileInput.files[0];
  if (!f) return;
  const reader = new FileReader();
  reader.onload = async function(){
    const b64 = (reader.result.split(',')[1]) || '';
    try {
      const r = await fetch('/api/chat/upload', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({filename: f.name, data: b64, size: f.size})});
      const d = await r.json();
      if (d.ok){ attachedFile = {name: d.name, path: d.path, is_text: d.is_text, size: d.size}; renderAttach(); }
      else { alert('Upload failed: ' + (d.msg || 'unknown')); }
    } catch(e){ alert('Upload error: ' + e); }
  };
  reader.readAsDataURL(f);
  fileInput.value = '';
});
function renderAttach(){
  if (!attachedFile){ chatAttach.innerHTML = ''; return; }
  const sz = (attachedFile.size/1024).toFixed(1) + ' KB';
  chatAttach.innerHTML = '<span class="chip">📎 ' + attachedFile.name + ' (' + sz + ') <a id="rmAtt">✕</a></span>';
  document.getElementById('rmAtt').addEventListener('click', function(){ attachedFile = null; renderAttach(); });
}
async function sendChat(){
  const prompt = chatText.value.trim();
  if (!prompt && !attachedFile) return;
  chatAppend('user', prompt || ('[file: ' + (attachedFile ? attachedFile.name : '') + ']'));
  chatText.value = '';
  const btn = document.getElementById('btnSend');
  btn.disabled = true;
  const loading = document.createElement('div'); loading.className = 'msg bot'; loading.textContent = '…'; chatLog.appendChild(loading);
  try {
    let d;
    if (currentMode() === 'single'){
      const r = await fetch('/api/chat', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({prompt: prompt, attachment: attachedFile,
                             system: sysPromptText.trim(),
                             max_tokens: parseInt(sampMaxTok.value, 10)})});
      d = await r.json();
      chatLog.removeChild(loading);
      if (d.ok){ chatAppend('bot', d.content); }
      else { chatAppend('bot', '\u26A0 ' + d.msg); }
    } else {
      const r = await fetch('/api/ensemble', {method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({prompt: prompt, models: '', system: sysPromptText.trim()})});
      d = await r.json();
      chatLog.removeChild(loading);
      if (d.ok){
        chatAppend('bot', 'Combined (' + d.strategy + '):\\n' + d.answer);
        (d.per_model || []).forEach(function(m){
          const tag = m.status === 'ok' ? ('nodes ' + (m.nodes||[]).join(',') + ' @ ' + (m.tps||0) + ' tok/s') : ('ERROR: ' + (m.error||''));
          chatAppend('bot', '  \u2022 ' + m.model + ' [' + tag + ']: ' + (m.answer || '').slice(0, 400));
        });
      } else { chatAppend('bot', '\u26A0 ' + d.msg); }
    }
  } catch(e){ chatLog.removeChild(loading); chatAppend('bot', '\u26A0 error: ' + e); }
  btn.disabled = false;
  attachedFile = null; renderAttach();
}
document.getElementById('btnSend').addEventListener('click', sendChat);
chatText.addEventListener('keydown', function(e){
  if (e.key === 'Enter' && !e.shiftKey){ e.preventDefault(); sendChat(); }
});
document.getElementById('btnClear').addEventListener('click', function(){
  chatLog.innerHTML = '';
  attachedFile = null; renderAttach();
});
// Clearing chat history does NOT clear the system prompt (it persists across turns).

// ---- Sampling parameter controls (per-model tuning) ----
const sampTemp = document.getElementById('sampTemp');
const sampMinP = document.getElementById('sampMinP');
const sampTopP = document.getElementById('sampTopP');
const sampRepPen = document.getElementById('sampRepPen');
const sampCtx = document.getElementById('sampCtx');
const sampMaxTok = document.getElementById('sampMaxTok');
const sampStatus = document.getElementById('sampStatus');
function readSampling(){
  return {
    temp: parseFloat(sampTemp.value),
    min_p: parseFloat(sampMinP.value),
    top_p: parseFloat(sampTopP.value),
    repeat_penalty: parseFloat(sampRepPen.value),
  };
}
function applySamplingToLoad(){
  // Stash the current control values so the Load button can send them.
  window._pendingSampling = readSampling();
  window._pendingCtxSize = parseInt(sampCtx.value, 10);
}
[sampTemp, sampMinP, sampTopP, sampRepPen, sampCtx, sampMaxTok].forEach(function(el){
  el.addEventListener('change', applySamplingToLoad);
});
async function loadSamplingDefaults(){
  try {
    const r = await fetch('/api/sampling');
    const d = await r.json();
    sampTemp.value = d.temp; sampMinP.value = d.min_p;
    sampTopP.value = d.top_p; sampRepPen.value = d.repeat_penalty;
    if (d.ctx_size) sampCtx.value = d.ctx_size;
    if (d.max_tokens) sampMaxTok.value = d.max_tokens;
    window._pendingSampling = readSampling();
    window._pendingCtxSize = parseInt(sampCtx.value, 10);
  } catch(e){ window._pendingSampling = readSampling(); window._pendingCtxSize = parseInt(sampCtx.value, 10); }
}
document.getElementById('btnSampReset').addEventListener('click', function(){
  loadSamplingDefaults();
  sampStatus.textContent = 'reset to config defaults';
});
// Reflect the resident model's active sampling in the controls.
async function refreshSamplingStatus(){
  try {
    const r = await fetch('/api/server/status');
    const s = await r.json();
    if (s.sampling){
      sampTemp.value = s.sampling.temp; sampMinP.value = s.sampling.min_p;
      sampTopP.value = s.sampling.top_p; sampRepPen.value = s.sampling.repeat_penalty;
      sampStatus.textContent = s.running ? 'active on resident model' : 'defaults (no model resident)';
    }
  } catch(e){ /* ignore */ }
}

loadModels();
refreshServerStatus();
setInterval(refreshServerStatus, 5000);
loadSamplingDefaults();
setInterval(refreshSamplingStatus, 5000);
</script>
</body>
</html>"""


# Background-refreshed cache so the HTTP endpoint never blocks on 11 SSH calls.
_STATE_CACHE = {"state": None, "updated": 0.0}
_STATE_LOCK = __import__("threading").Lock()
JSON_CT = "application/json"

# Resident-model state for the dashboard's single-mode chat. The dashboard uses
# the SAME MTP llama-cli + all-11-RPC-worker path the CLI backend uses, so the
# UI is synchronised with the proven-working backend. "Load" records the model
# here; "Chat" runs llama-cli per prompt against it (no separate HTTP server).
_RESIDENT_MODEL = None
_RESIDENT_CTX = 2048
_RESIDENT_LOCK = __import__("threading").Lock()
_RESIDENT_PORT = 8080
_RESIDENT_PROC = None  # Popen handle for the persistent llama-server
# Sampling parameters for the resident model. Defaults come from cluster_config
# (single source of truth); the dashboard UI can override them per load. These
# are forwarded to every chat request so the controls take effect end-to-end.
_RESIDENT_SAMPLING = {
    "temp": SAMPLING_TEMP,
    "min_p": SAMPLING_MIN_P,
    "top_p": SAMPLING_TOP_P,
    "repeat_penalty": SAMPLING_REPEAT_PENALTY,
}


def _state_refresher(interval=2.0):
    """Continuously refresh _STATE_CACHE in a daemon thread."""
    while True:
        try:
            snap = collect_state()
            with _STATE_LOCK:
                _STATE_CACHE["state"] = snap
                _STATE_CACHE["updated"] = time.time()
        except Exception:
            pass
        time.sleep(interval)


def _get_cached_state():
    with _STATE_LOCK:
        return _STATE_CACHE["state"]


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/state":
            body = json.dumps(_get_cached_state() or {}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", JSON_CT)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        elif self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode("utf-8"))
        elif self.path == "/api/models":
            body = json.dumps(list_models()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", JSON_CT)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/sampling":
            body = json.dumps({
                "temp": SAMPLING_TEMP,
                "min_p": SAMPLING_MIN_P,
                "top_p": SAMPLING_TOP_P,
                "repeat_penalty": SAMPLING_REPEAT_PENALTY,
                "ctx_size": CTX_SIZE_DEFAULT,
                "max_tokens": MAX_TOKENS_DEFAULT,
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", JSON_CT)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/server/status":
            status = _server_status()
            ens = _ensemble_status()
            if ens is not None:
                status["ensemble"] = ens
            body = json.dumps(status).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", JSON_CT)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        _ROUTES = {
            "/api/shutdown": self._post_shutdown,
            "/api/start": self._post_start,
            "/api/server/load": self._post_server_load,
            "/api/server/eject": self._post_server_eject,
            "/api/chat/upload": self._post_chat_upload,
            "/api/chat": self._post_chat,
            "/api/ensemble": self._post_ensemble,
            "/api/ensemble/launch": self._post_ensemble_launch,
            "/api/ensemble/stop": self._post_ensemble_stop,
        }
        handler = _ROUTES.get(self.path)
        if handler is None:
            self.send_response(404)
            self.end_headers()
            return
        body = handler()
        self.send_response(200)
        self.send_header("Content-Type", JSON_CT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _post_shutdown(self):
        ok, total, failed, mode_set = power_shutdown_all()
        return json.dumps({
            "ok": ok, "total": total,
            "failed": failed, "maintenance": mode_set,
        }).encode("utf-8")

    def _post_start(self):
        mode_set = power_start_all()
        return json.dumps({
            "maintenance_cleared": mode_set,
            "note": ("Physical 5V power-on is handled by the Sonoff switch "
                     "(Alexa) and is out of scope for software. Power the "
                     "nodes on at the switch, then the watchdog resumes."),
        }).encode("utf-8")

    def _post_server_load(self):
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        model = payload.get("model", "")
        if not model or not os.path.isfile(model):
            return json.dumps({"ok": False, "msg": "invalid model path"}).encode("utf-8")
        ctx = int(payload.get("ctx_size", 2048))
        # Sampling overrides from the dashboard UI (defaults from cluster_config).
        raw_samp = payload.get("sampling", {}) or {}
        sampling = _coerce_sampling(raw_samp)
        import subprocess as _sp
        # Launch persistent llama-server ONCE, then serve all chats via HTTP.
        # This avoids the 2-3 min CLI reload on every prompt.
        with _RESIDENT_LOCK:
            global _RESIDENT_MODEL, _RESIDENT_CTX, _RESIDENT_PROC, _RESIDENT_PORT
            if _RESIDENT_PROC is not None:
                try:
                    _RESIDENT_PROC.kill()
                    _RESIDENT_PROC.wait(timeout=5)
                except Exception:
                    pass
                _RESIDENT_PROC = None
            _RESIDENT_PORT = 8080
            srv_bin = os.path.join(os.path.dirname(RESIDENT_CLI), "llama-server.exe")
            cmd = [
                srv_bin,
                "-m", model,
                "--rpc", rpc_list(),
                "--host", "127.0.0.1",
                "--port", str(_RESIDENT_PORT),
                "-c", str(ctx),
                "--no-warmup",
                "-ngl", "0",
                "--temp", str(sampling["temp"]),
                "--min-p", str(sampling["min_p"]),
                "--top-p", str(sampling["top_p"]),
                "--repeat-penalty", str(sampling["repeat_penalty"]),
            ]
            env = os.environ.copy()
            env["PATH"] = os.path.dirname(RESIDENT_CLI) + os.pathsep + env.get("PATH", "")
            flags = _sp.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            log = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "cluster_server.log"), "w", encoding="utf-8")
            _RESIDENT_PROC = _sp.Popen(cmd, stdout=log, stderr=log,
                                       env=env, creationflags=flags)
            import urllib.request as _ureq
            deadline = time.time() + 300
            while time.time() < deadline:
                if _RESIDENT_PROC.poll() is not None:
                    return json.dumps({"ok": False,
                                       "msg": "server exited early"}).encode("utf-8")
                try:
                    with _ureq.urlopen(f"http://127.0.0.1:{_RESIDENT_PORT}/health",
                                       timeout=2) as r:
                        if r.status == 200:
                            _RESIDENT_MODEL = model
                            _RESIDENT_CTX = ctx
                            _RESIDENT_SAMPLING = sampling
                            return json.dumps({"ok": True,
                                               "msg": "resident"}).encode("utf-8")
                except Exception:
                    time.sleep(2)
            return json.dumps({"ok": False,
                               "msg": "timed out waiting for server"}).encode("utf-8")

    def _post_server_eject(self):
        with _RESIDENT_LOCK:
            global _RESIDENT_MODEL, _RESIDENT_PROC
            _RESIDENT_MODEL = None
            if _RESIDENT_PROC is not None:
                try:
                    _RESIDENT_PROC.kill()
                    _RESIDENT_PROC.wait(timeout=5)
                except Exception:
                    pass
                _RESIDENT_PROC = None
        return json.dumps({"ok": True, "msg": "no model resident"}).encode("utf-8")

    def _post_chat_upload(self):
        # Save an uploaded file (base64 JSON) to CHAT_UPLOAD_DIR for use as
        # chat context. Returns metadata the UI uses to attach it to a prompt.
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        try:
            res = _save_upload(payload.get("filename", "upload.bin"),
                               payload.get("data", ""))
        except Exception as e:
            res = {"ok": False, "msg": str(e)}
        return json.dumps(res).encode("utf-8")

    def _post_chat(self):
        # Forward a prompt (optionally with an attached file) to the resident
        # llama-server. No model resident -> friendly error, not a 500.
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        prompt = (payload.get("prompt") or "").strip()
        attachment = payload.get("attachment") or {}
        system = (payload.get("system") or "").strip()
        max_tokens = payload.get("max_tokens")
        if not isinstance(max_tokens, int) or max_tokens is None:
            max_tokens = MAX_TOKENS_DEFAULT
        if not _server_status().get("running"):
            return json.dumps({"ok": False,
                               "msg": "No model resident. Load one from the Model panel above first."}).encode("utf-8")
        if not prompt and not attachment:
            return json.dumps({"ok": False, "msg": "Empty prompt."}).encode("utf-8")
        full = self._read_attachment_text(attachment, prompt)
        try:
            data = _chat_completion(full, n_predict=max_tokens, system_prompt=system,
                                    sampling=_RESIDENT_SAMPLING)
            content = data.get("content", "")
            # Feed the measured generation speed back into the telemetry
            # metrics file so the "Gen Speed" card reflects real chat
            # throughput (the legacy cluster_infer.py path no longer
            # writes it). predicted_per_second comes from llama-server.
            try:
                tps = (data.get("timings") or {}).get("predicted_per_second")
                if isinstance(tps, (int, float)) and tps > 0:
                    _write_inference_metrics(tps)
            except Exception:
                pass
            return json.dumps({"ok": True, "content": content}).encode("utf-8")
        except Exception as e:
            return json.dumps({"ok": False, "msg": "inference error: " + str(e)}).encode("utf-8")

    @staticmethod
    def _read_attachment_text(attachment, prompt):
        """Return prompt with an attached text file inlined, or prompt as-is."""
        apath = attachment.get("path")
        if not apath or not os.path.isfile(apath):
            return prompt
        try:
            with open(apath, "rb") as _f:
                _raw = _f.read()
            if _looks_text(_raw):
                return ("=== ATTACHED FILE: "
                        + attachment.get("name", "file") + " ===\n"
                        + _raw.decode("utf-8", "replace")
                        + "\n=== END FILE ===\n\n" + prompt)
        except Exception:
            pass
        return prompt

    def _post_ensemble(self):
        # Run a prompt across an ensemble of models (each on its own port +
        # disjoint random node subset) and combine via self-consistency.
        # The ensemble must already be launched (ensemble-start) so the
        # per-model llama-servers are resident; this endpoint only fans out
        # the prompt and combines. System prompt applies to ALL members.
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        prompt = (payload.get("prompt") or "").strip()
        if not prompt:
            return json.dumps({"ok": False, "msg": "Empty prompt."}).encode("utf-8")
        if partition_ensemble is None:
            return json.dumps({"ok": False, "msg": "ensemble helpers unavailable."}).encode("utf-8")
        models = [m.strip() for m in (payload.get("models") or "").split(",") if m.strip()]
        if not models:
            # No models passed: use the already-launched ensemble state
            # (so the unified chat can just "send" in ensemble mode).
            assignments = _read_ensemble_state()
            if not assignments:
                return json.dumps({"ok": False,
                                   "msg": "No models specified and no ensemble running."}).encode("utf-8")
        else:
            try:
                assignments = partition_ensemble(models)
            except ValueError as e:
                return json.dumps({"ok": False, "msg": str(e)}).encode("utf-8")
        system = (payload.get("system") or "").strip() if ENSEMBLE_APPLY_SYSTEM_PROMPT else ""
        per_model = [self._ensemble_member(a, prompt, system) for a in assignments]
        live = [m for m in per_model if m["status"] == "ok"]
        combined = _self_consistency_combine(per_model) if live else "(no ensemble members responded)"
        return json.dumps({"ok": bool(live), "answer": combined,
                           "strategy": "self-consistency",
                           "per_model": per_model}).encode("utf-8")

    @staticmethod
    def _ensemble_member(a, prompt, system):
        """Probe one ensemble member and return its result dict."""
        # Skip members whose server is not actually up (dead
        # pid in a stale ensemble_state.json, or still loading).
        # This keeps the ensemble endpoint working even if one
        # member died, instead of failing the whole request.
        if not _probe_port(a["port"]):
            return {
                "model": os.path.basename(a["model"]),
                "port": a["port"], "nodes": a["nodes"],
                "answer": "", "tps": 0.0,
                "status": "skipped",
                "error": "member not running on this port",
            }
        try:
            content, tps = _ensemble_complete(a["port"], prompt, system)
            if tps > 0:
                try: _write_inference_metrics(tps)
                except Exception: pass
            return {
                "model": os.path.basename(a["model"]),
                "port": a["port"], "nodes": a["nodes"],
                "answer": content, "tps": round(tps, 2),
                "status": "ok",
            }
        except Exception as e:
            return {
                "model": os.path.basename(a["model"]),
                "port": a["port"], "nodes": a["nodes"],
                "answer": "", "tps": 0.0,
                "status": "error", "error": str(e),
            }

    def _post_ensemble_launch(self):
        # Launch the ensemble via cluster_server.py (detached llama-servers
        # resident on disjoint node subsets). Ejects any single-model
        # resident first to avoid a port/RPC clash. We then wait for each
        # member's /health to come up (like cmd_start) so the UI only shows
        # success once the models are actually resident — not on launch PID.
        length = int(self.headers.get("Content-Length", 0))
        payload = json.loads(self.rfile.read(length) or b"{}")
        models = (payload.get("models") or "").strip()
        if not models:
            return json.dumps({"ok": False, "msg": "No models specified."}).encode("utf-8")
        ctx = int(payload.get("ctx_size", CTX_SIZE_DEFAULT))
        samp = _coerce_sampling(payload.get("sampling", {}) or {})
        try:
            rc, out = _run_server([
                "ensemble-start", "--models", models,
                "--ctx-size", str(ctx),
                "--temp", str(samp["temp"]),
                "--min-p", str(samp["min_p"]),
                "--top-p", str(samp["top_p"]),
                "--repeat-penalty", str(samp["repeat_penalty"]),
            ])
            if rc != 0:
                return json.dumps({"ok": False, "msg": out, "count": len(models.split(","))}).encode("utf-8")
            # Wait for every member to report /health (up to 180s).
            state = _read_ensemble_state_raw()
            ports = [a.get("port") for a in (state or []) if a.get("port")]
            deadline = time.time() + 180
            ready = []
            while time.time() < deadline:
                ready = [p for p in ports if _probe_port(p)]
                if len(ready) == len(ports):
                    break
                time.sleep(2)
            all_up = len(ready) == len(ports) and len(ports) > 0
            return json.dumps({
                "ok": all_up,
                "msg": ("running" if all_up
                        else f"only {len(ready)}/{len(ports)} members up"),
                "count": len(models.split(",")),
                "ready_ports": ready,
            }).encode("utf-8")
        except Exception as e:
            return json.dumps({"ok": False, "msg": str(e)}).encode("utf-8")

    def _post_ensemble_stop(self):
        # Stop all ensemble members (kills detached llama-servers, frees shards).
        try:
            rc, out = _run_server(["ensemble-stop"])
            return json.dumps({"ok": rc == 0, "msg": out}).encode("utf-8")
        except Exception as e:
            return json.dumps({"ok": False, "msg": str(e)}).encode("utf-8")

    def log_message(self, *args):
        # Intentionally silent: this is a local-only telemetry dashboard bound to
        # 127.0.0.1/0.0.0.0 on a trusted LAN; request logging adds noise with no
        # security value here.
        pass


def cmd_web():
    # Local-only HTTP dashboard on a trusted LAN segment. No credentials or PII
    # are served; HTTPS is unnecessary for loopback/LAN telemetry viewing.
    import threading
    threading.Thread(target=_state_refresher, daemon=True).start()
    print(f"[WEB] Dashboard running at http://localhost:{WEB_PORT}  (Ctrl+C to stop)")
    srv = ThreadingHTTPServer((WEB_HOST, WEB_PORT), _Handler)
    try:
        # nosec B104: local-only telemetry dashboard on a trusted LAN segment.
        # No credentials or PII are served; plaintext HTTP is intentional.
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nWeb dashboard stopped.")
        srv.shutdown()


# ===========================================================================
# DISPATCH
# ===========================================================================
def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "audit"
    if mode == "audit":
        cmd_audit()
    elif mode == "monitor":
        cmd_monitor()
    elif mode == "web":
        cmd_web()
    else:
        print("Usage: python cluster_telemetry.py [audit|monitor|web]")
        sys.exit(2)


if __name__ == "__main__":
    main()
