"""
cluster_mcp_server.py — MCP server for the 11-node Jetson Nano cluster.

Runs on the Windows PC (orchestrator). Exposes cluster management as MCP tools so
an agent (VS Code Copilot / Claude Desktop) can drive the cluster.

Tool namespaces:
  cluster.rpc.*    — wrap existing llama.cpp RPC ops (health, deploy, telemetry, capture)
  cluster.fleet.*  — node fleet state, fault tolerance, scaling benchmark
  cluster.gemm.*   — Tier 1 star-topology FP16 matrix sharding (PyCUDA workers)
  cluster.embed.*  — Tier 1 token->embedding sharding (PyCUDA workers)
  cluster.ring.*   — Tier 2 MoE expert-parallel ring (PyCUDA workers)
  cluster.model.*  — model registry + resumable download

All changeable facts come from cluster_config.py (single source of truth).
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from mcp.server.fastmcp import FastMCP

import cluster_config as cfg

mcp = FastMCP("jetson-cluster")


# ===========================================================================
# SHARED HELPERS
# ===========================================================================
def _run(cmd, timeout=60, shell=False):
    """Run a command, return (rc, stdout, stderr)."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=shell)
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "timeout"
    except Exception as e:  # noqa: BLE001
        return -2, "", str(e)


def _ssh(ip, command, timeout=15):
    cmd = ["ssh"] + cfg.SSH_OPTS + [f"{cfg.SSH_USER}@{ip}", command]
    return _run(cmd, timeout=timeout)


def _ssh_launch(ip, command):
    """Launch a long-lived remote daemon without blocking (ssh -f)."""
    cmd = ["ssh", "-f"] + cfg.SSH_OPTS + [f"{cfg.SSH_USER}@{ip}", command]
    return _run(cmd, timeout=15)


def _push(ip, local_src, remote_dst, timeout=60):
    cmd = ["scp"] + cfg.SSH_OPTS + [local_src, f"{cfg.SSH_USER}@{ip}:{remote_dst}"]
    return _run(cmd, timeout=timeout)


# ===========================================================================
# cluster.rpc.*  — wrap existing llama.cpp RPC ops
# ===========================================================================
@mcp.tool()
def rpc_audit() -> str:
    """One-shot deploy-gate health audit of all 11 nodes (RPC port + RAM + thermal + GUI)."""
    _telemetry = os.path.join(cfg.CODE_DIR, "cluster_telemetry.py")
    _, out, err = _run([sys.executable, _telemetry, "audit"], timeout=120)
    return out + (f"\n[stderr]\n{err}" if err else "")


@mcp.tool()
def rpc_deploy(mode: str = "launch") -> str:
    """Manage llama.cpp RPC daemons. mode: launch | terminate | init | poweroff.

    launch   = start rpc-server (via mlockall_wrapper) on all 11 nodes
    terminate= kill rpc-server on all 11 nodes
    init     = nvpmodel -m 0 + jetson_clocks on all 11 nodes
    poweroff = shutdown -h now on all 11 nodes
    """
    _deploy = os.path.join(cfg.CODE_DIR, "cluster_deploy.py")
    _, out, err = _run([sys.executable, _deploy, mode], timeout=180)
    return out + (f"\n[stderr]\n{err}" if err else "")


@mcp.tool()
def rpc_capture(prompt_file: str, model_key: str, tokens: int = 1024,
                out_dir: str = "", grammar_file: str = "") -> str:
    """Run cluster inference via llama-cli.exe and capture formatted output.

    prompt_file : path to a .txt prompt on the PC
    model_key   : key into the model registry (e.g. 'llama-3.3-70b-iq3_xs')
    tokens      : max tokens to generate
    out_dir     : output directory (default C:\\Outputs)
    grammar_file: optional .gbnf grammar for structured JSON output
    """
    m = cfg.model_entry(model_key)
    if not os.path.exists(m["local"]):
        return f"ERROR: model file not found: {m['local']}"
    if not os.path.exists(prompt_file):
        return f"ERROR: prompt file not found: {prompt_file}"
    _ps1 = os.path.join(cfg.CODE_DIR, "phase10_capture.ps1")
    args = ["pwsh", _ps1, "-PromptFile", prompt_file, "-Model", m["local"],
            "-Tokens", str(tokens)]
    if out_dir:
        args += ["-OutDir", out_dir]
    if grammar_file:
        args += ["-GrammarFile", grammar_file]
    _, out, err = _run(args, timeout=600)
    return out + (f"\n[stderr]\n{err}" if err else "")


@mcp.tool()
def rpc_telemetry_snapshot() -> str:
    """Return a JSON snapshot of cluster state (nodes, RAM, temps, net, inference tok/s)."""
    _telemetry = os.path.join(cfg.CODE_DIR, "cluster_telemetry.py")
    # cluster_telemetry.py has no JSON mode; replicate collect_state via import.
    try:
        sys.path.insert(0, cfg.CODE_DIR)
        import cluster_telemetry as ct  # type: ignore
        state = ct.collect_state()
        return json.dumps(state, indent=2)
    except Exception as e:  # noqa: BLE001
        return f"ERROR importing telemetry: {e}"


# ===========================================================================
# cluster.fleet.*  — node fleet state, fault tolerance, scaling
# ===========================================================================
@mcp.tool()
def fleet_nodes() -> str:
    """List all 11 nodes with live RPC reachability (TCP probe, no SSH needed)."""
    import socket
    rows = []
    for name, ip in zip(cfg.NODE_NAMES, cfg.NODE_IPS):
        up = False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                up = s.connect_ex((ip, cfg.RPC_PORT)) == 0
        except Exception:  # noqa: BLE001
            up = False
        rows.append({"name": name, "ip": ip, "rpc_up": up})
    online = sum(1 for r in rows if r["rpc_up"])
    return json.dumps({"online": online, "total": len(rows), "nodes": rows}, indent=2)


@mcp.tool()
def fleet_ssh_health() -> str:
    """Per-node SSH health: UMA RAM available, GUI active, max thermal (deg C)."""
    def probe(ip):
        ram_gb, ui, temp = 0.0, False, None
        code, out, _ = _ssh(ip, "awk '/MemAvailable/ {print $2}' /proc/meminfo")
        if code == 0 and out.strip():
            ram_gb = int(out.strip()) / (1024 * 1024)
        _, o2, _ = _ssh(ip, "pgrep -f 'Xorg|gdm|lightdm'")
        ui = bool(o2.strip())
        _, o3, _ = _ssh(ip, "timeout 2 tegrastats --interval 1000 2>/dev/null | head -1")
        import re
        temps = [float(t) for t in re.findall(r"@(\d+(?:\.\d+)?)C", o3)]
        temp = max(temps) if temps else None
        return {"ip": ip, "ram_gb": round(ram_gb, 2), "gui_active": ui, "max_temp_c": temp}
    with ThreadPoolExecutor(max_workers=len(cfg.NODE_IPS)) as ex:
        results = list(ex.map(probe, cfg.NODE_IPS))
    return json.dumps(results, indent=2)


@mcp.tool()
def fleet_rebalance(shard_map: str) -> str:
    """Reassign compute shards after a node dropout. shard_map is JSON:
    {"<node_ip_or_index>": [shard_ids...]}. Validates no shard is double-assigned
    and all 11 shards are covered. Returns the accepted plan or an error.

    This is the fault-tolerance action: when fleet_nodes shows a dead node, the
    orchestrator calls this to redistribute that node's shards to live nodes.
    """
    try:
        plan = json.loads(shard_map)
    except Exception as e:  # noqa: BLE001
        return f"ERROR: invalid JSON: {e}"
    # Normalize keys to IPs
    norm = {}
    for k, v in plan.items():
        ip = cfg.NODE_IPS[int(k)] if k.isdigit() else k
        norm[ip] = list(v)
    all_shards = sorted({s for v in norm.values() for s in v})
    expected = list(range(cfg.SHARD_COUNT))
    if all_shards != expected:
        return (f"ERROR: shard coverage mismatch. got {all_shards}, "
                f"expected {expected}")
    # Persist the plan so gemm/embed/ring orchestrators read it.
    plan_path = os.path.join(cfg.CODE_DIR, "shard_plan.json")
    with open(plan_path, "w", encoding="utf-8") as f:
        json.dump(norm, f, indent=2)
    return json.dumps({"accepted": True, "plan": norm}, indent=2)


@mcp.tool()
def fleet_scaling_benchmark(rows: int = 2200, cols: int = 500, shards: int = 11) -> str:
    """Measure GEMM scaling efficiency: time to shard+compute+reassemble a matrix
    across N live nodes vs 1 node. Returns per-shard-count timings.

    This is the '1 node vs 11 nodes' proof-of-principle measurement. Requires the
    GEMM workers (cluster.gemm.*) to be running on the targeted nodes.
    """
    import numpy as np
    if shards < 1 or shards > cfg.SHARD_COUNT:
        return f"ERROR: shards must be 1..{cfg.SHARD_COUNT}"
    live = [ip for ip in cfg.NODE_IPS[:shards]
            if _tcp_up(ip, cfg.GEMM_PORT)]
    if not live:
        return "ERROR: no GEMM workers reachable on targeted nodes (start them via gemm_start_workers)."
    results = {}
    rng = np.random.default_rng(0)
    master = rng.standard_normal((rows, cols)).astype(np.float16)
    for n in (1, shards):
        targets = live[:n]
        t0 = time.time()
        shards_arr = np.array_split(master, len(targets), axis=0)
        loop = asyncio.new_event_loop()
        try:
            reassembled = loop.run_until_complete(
                _gemm_distribute(targets, shards_arr))
        finally:
            loop.close()
        dt = time.time() - t0
        results[str(n)] = {
            "nodes": n, "elapsed_s": round(dt, 4),
            "shape": list(reassembled.shape) if reassembled is not None else None,
        }
    return json.dumps(results, indent=2)


# ===========================================================================
# cluster.gemm.*  — Tier 1 star-topology FP16 matrix sharding
# ===========================================================================
WORKERS_DIR = os.path.join(cfg.CODE_DIR, "mcp", "workers")


@mcp.tool()
def gemm_push_workers() -> str:
    """SCP jetson_worker.py (FP16 matmul socket server) to all 11 nodes."""
    src = os.path.join(WORKERS_DIR, "jetson_worker.py")
    if not os.path.exists(src):
        return f"ERROR: worker script missing: {src}"
    out = []
    for ip in cfg.NODE_IPS:
        rc, _, e = _push(ip, src, "/home/jetson/jetson_worker.py")
        out.append(f"{ip}: rc={rc} {'ok' if rc == 0 else e.strip()}")
    return "\n".join(out)


@mcp.tool()
def gemm_start_workers() -> str:
    """Launch jetson_worker.py on all 11 nodes (port 9999) via ssh -f."""
    cmd = (f"setsid nohup python3 /home/jetson/jetson_worker.py "
           f"--port {cfg.GEMM_PORT} < /dev/null > /home/jetson/gemm.log 2>&1 &")
    out = []
    for ip in cfg.NODE_IPS:
        rc, _, e = _ssh_launch(ip, cmd)
        out.append(f"{ip}: rc={rc} {'launched' if rc == 0 else e.strip()}")
    return "\n".join(out)


@mcp.tool()
def gemm_stop_workers() -> str:
    """Kill jetson_worker.py on all 11 nodes."""
    out = []
    for ip in cfg.NODE_IPS:
        rc, _, _ = _ssh(ip, "pkill -9 -f '[j]etson_worker.py' || true")
        out.append(f"{ip}: rc={rc}")
    return "\n".join(out)


@mcp.tool()
def gemm_run(rows: int = 2200, cols: int = 500) -> str:
    """Distribute a random float16 matrix across live GEMM workers, compute A@A^T
    per shard on the Jetsons, reassemble, and report timing + shape."""
    import numpy as np
    live = [ip for ip in cfg.NODE_IPS if _tcp_up(ip, cfg.GEMM_PORT)]
    if not live:
        return "ERROR: no GEMM workers running. Call gemm_start_workers first."
    rng = np.random.default_rng(0)
    master = rng.standard_normal((rows, cols)).astype(np.float16)
    shards_arr = np.array_split(master, len(live), axis=0)
    t0 = time.time()
    loop = asyncio.new_event_loop()
    try:
        reassembled = loop.run_until_complete(_gemm_distribute(live, shards_arr))
    finally:
        loop.close()
    dt = time.time() - t0
    if reassembled is None:
        return "ERROR: one or more shards failed (see fleet_nodes / gemm_start_workers)."
    return json.dumps({
        "nodes_used": len(live), "elapsed_s": round(dt, 4),
        "out_shape": list(reassembled.shape),
    }, indent=2)


# ===========================================================================
# cluster.embed.*  — Tier 1 token->embedding sharding
# ===========================================================================
@mcp.tool()
def embed_push_workers() -> str:
    """SCP jetson_embedding_worker.py to all 11 nodes."""
    src = os.path.join(WORKERS_DIR, "jetson_embedding_worker.py")
    if not os.path.exists(src):
        return f"ERROR: worker script missing: {src}"
    out = []
    for ip in cfg.NODE_IPS:
        rc, _, e = _push(ip, src, "/home/jetson/jetson_embedding_worker.py")
        out.append(f"{ip}: rc={rc} {'ok' if rc == 0 else e.strip()}")
    return "\n".join(out)


@mcp.tool()
def embed_start_workers() -> str:
    """Launch jetson_embedding_worker.py on all 11 nodes (port 9998)."""
    cmd = (f"setsid nohup python3 /home/jetson/jetson_embedding_worker.py "
           f"--port {cfg.EMBED_PORT} < /dev/null > /home/jetson/embed.log 2>&1 &")
    out = []
    for ip in cfg.NODE_IPS:
        rc, _, e = _ssh_launch(ip, cmd)
        out.append(f"{ip}: rc={rc} {'launched' if rc == 0 else e.strip()}")
    return "\n".join(out)


@mcp.tool()
def embed_stop_workers() -> str:
    """Kill jetson_embedding_worker.py on all 11 nodes."""
    out = []
    for ip in cfg.NODE_IPS:
        rc, _, _ = _ssh(ip, "pkill -9 -f '[j]etson_embedding_worker.py' || true")
        out.append(f"{ip}: rc={rc}")
    return "\n".join(out)


@mcp.tool()
def embed_instruction(text: str, model_key: str = "", as_b64: bool = True) -> str:
    """FP16 instruction-payload path to the small models.

    The small LLMs receive TEXT instructions, but an agent can ALSO request the
    float16 embedding of an instruction text. This tokenizes `text` with the
    REAL model vocab (via llama-tokenize.exe on the model's GGUF), streams the
    token-ids to the embedding workers (port 9998, float16 projection kernel),
    and returns the resulting (num_tokens, EMBEDDING_DIM) float16 matrix.

    model_key : optional registry key (e.g. 'phi-3-mini-4k-instruct-q6_k') to
                pick that model's tokenizer; empty = family fallback / mock.
    as_b64=True  -> returns base64 (ready to attach to a task JSON payload)
    as_b64=False -> returns a compact JSON {shape, dtype, sample_row}

    This is the "instructions in FP16" companion: text goes to the LLM, the
    float16 embedding goes alongside it as a structured seed/context vector.
    """
    import base64
    import numpy as np
    try:
        from embed_client import embed_text_sync, tokenize
    except Exception:  # pragma: no cover
        sys.path.insert(0, cfg.CODE_DIR)
        from embed_client import embed_text_sync, tokenize
    mk = model_key or None
    emb = embed_text_sync(text, model_key=mk)
    if emb is None:
        return ("ERROR: no embedding workers live. Call embed_start_workers first "
                "(the FP16 instruction path needs the 9998 tier).")
    if as_b64:
        b64 = base64.b64encode(emb.astype(np.float16).tobytes()).decode("ascii")
        return json.dumps({
            "text": text, "model_key": model_key,
            "tokens": tokenize(text, mk).tolist(),
            "shape": list(emb.shape), "dtype": "float16",
            "fp16_b64": b64,
        }, indent=2)
    return json.dumps({
        "text": text, "model_key": model_key,
        "tokens": tokenize(text, mk).tolist(),
        "shape": list(emb.shape), "dtype": "float16",
        "sample_row_0": [round(float(x), 4) for x in emb[0].tolist()],
    }, indent=2)


@mcp.tool()
def embed_run(paragraphs: int = 110, tokens_per_paragraph: int = 1000) -> str:
    """Tokenize mock corpus -> stream token-id shards to embedding workers (throttled
    by MAX_CONCURRENT_NET_STREAMS) -> reassemble embedding matrix. Reports timing."""
    import numpy as np
    live = [ip for ip in cfg.NODE_IPS if _tcp_up(ip, cfg.EMBED_PORT)]
    if not live:
        return "ERROR: no embedding workers running. Call embed_start_workers first."
    rng = np.random.default_rng(0)
    corpus = rng.integers(0, cfg.VOCAB_SIZE - 1,
                          size=(paragraphs, tokens_per_paragraph), dtype=np.int32)
    t0 = time.time()
    loop = asyncio.new_event_loop()
    try:
        matrix = loop.run_until_complete(_embed_distribute(live, corpus))
    finally:
        loop.close()
    dt = time.time() - t0
    if matrix is None:
        return "ERROR: one or more embedding shards failed."
    return json.dumps({
        "nodes_used": len(live), "elapsed_s": round(dt, 4),
        "embedding_shape": list(matrix.shape),
    }, indent=2)


# ===========================================================================
# cluster.ring.*  — Tier 2 MoE expert-parallel ring
# ===========================================================================
@mcp.tool()
def ring_push_workers() -> str:
    """SCP jetson_ring_worker.py to all 11 nodes (ring topology, port 8888)."""
    src = os.path.join(WORKERS_DIR, "jetson_ring_worker.py")
    if not os.path.exists(src):
        return f"ERROR: worker script missing: {src}"
    out = []
    for ip in cfg.NODE_IPS:
        rc, _, e = _push(ip, src, "/home/jetson/jetson_ring_worker.py")
        out.append(f"{ip}: rc={rc} {'ok' if rc == 0 else e.strip()}")
    return "\n".join(out)


@mcp.tool()
def ring_start_workers() -> str:
    """Launch the ring: Jetson 10 first ... down to Jetson 0, so downstream sockets
    are listening before data arrives (per the design doc's boot order)."""
    out = []
    for idx in reversed(range(cfg.SHARD_COUNT)):
        ip = cfg.NODE_IPS[idx]
        next_ip = cfg.NODE_IPS[(idx + 1) % cfg.SHARD_COUNT]
        cmd = (f"setsid nohup python3 /home/jetson/jetson_ring_worker.py "
               f"--port {cfg.RING_PORT} --next-ip {next_ip} --next-port {cfg.RING_PORT} "
               f"< /dev/null > /home/jetson/ring.log 2>&1 &")
        rc, _, e = _ssh_launch(ip, cmd)
        out.append(f"{ip}->next {next_ip}: rc={rc} {'launched' if rc == 0 else e.strip()}")
    return "\n".join(out)


@mcp.tool()
def ring_stop_workers() -> str:
    """Kill jetson_ring_worker.py on all 11 nodes."""
    out = []
    for ip in cfg.NODE_IPS:
        rc, _, _ = _ssh(ip, "pkill -9 -f '[j]etson_ring_worker.py' || true")
        out.append(f"{ip}: rc={rc}")
    return "\n".join(out)


@mcp.tool()
def ring_run(model_key: str = "deepseek-coder-v2-lite-q4_k_m",
             batches: int = 3) -> str:
    """Drive the MoE ring: PC does Attention+Routing, Jetsons run expert FFN via the
    ring, final hidden-state tensor returns to PC. model_key selects the MoE weights
    (currently deepseek-coder-v2-lite). Reports batches pumped + timing.

    NOTE: the ring worker's expert GEMM kernel is research-grade (stub in the source
    doc); this tool validates the pipeline/transport, not production MoE quality.
    """
    m = cfg.model_entry(model_key)
    if m["kind"] != "moe":
        return f"ERROR: {model_key} is '{m['kind']}', not 'moe'. Ring needs an MoE model."
    if not _tcp_up(cfg.NODE_IPS[0], cfg.RING_PORT):
        return f"ERROR: ring head node ({cfg.NODE_IPS[0]}) not listening. Call ring_start_workers."
    t0 = time.time()
    loop = asyncio.new_event_loop()
    try:
        ok = loop.run_until_complete(_ring_pump(cfg.NODE_IPS[0], batches))
    finally:
        loop.close()
    dt = time.time() - t0
    return json.dumps({
        "model": model_key, "batches": batches,
        "elapsed_s": round(dt, 4), "ring_ok": ok,
    }, indent=2)


# ===========================================================================
# cluster.power.*  — OS shutdown (graceful) + power-on verify
# ---------------------------------------------------------------------------
# IMPORTANT SCOPE SPLIT (see Work Plan Phase 15):
#   * OS Shutdown  = graceful SSH halt of the 11 boards. This is a SOFTWARE
#     action driven by the dashboard button -> this tool.
#   * Power (5V cut / restore) = a Sonoff switch toggled by Alexa voice. This is
#     OUT OF SCOPE for software — there is no API the dashboard can call. The
#     dashboard only REACTS (polls for nodes coming up after "Alexa, on").
# The two must stay distinct: the button is labelled "OS Shutdown", never
# "Power Off", so nobody confuses a graceful halt with a hard power cut.
# ===========================================================================
@mcp.tool()
def power_os_shutdown(confirm: bool = False) -> str:
    """Gracefully halt all 11 Jetson boards via SSH (OS shutdown, NOT power cut).

    Order: workers (1-10) FIRST, Nano Zero (NFS server) LAST — so workers unmount
    node0's NFS cleanly instead of hanging on a dead server. Sets cluster mode to
    'maintenance' first so the fault-tolerant watchdog stands down and does NOT
    fight the shutdown (no re-slice / re-admit spam).

    confirm: MUST be True (safety gate — single-click destructive action on 11 nodes).
    Returns per-node result: acknowledged | timeout | unreachable.
    """
    if not confirm:
        return ("ERROR: confirm=True required. This halts 11 boards. "
                "Physical power (5V) is a separate Sonoff/Alexa action.")
    # 1) Flip the shared flag so the watchdog stands down (single source of truth).
    cfg.set_cluster_mode(cfg.CLUSTER_MODE_MAINTENANCE)
    # 2) Order: workers first (skip node0 at index 0), node0 last.
    order = [ip for ip in cfg.NODE_IPS if ip != cfg.NODE0_IP] + [cfg.NODE0_IP]
    out = []
    for ip in order:
        # Graceful: stop rpc-server, unmount NFS, sync, then halt.
        cmd = ("sudo pkill -9 -f '[r]pc-server' || true; "
               "sudo umount -f /mnt/nano-ssd 2>/dev/null || true; "
               "sync; sudo shutdown -h now")
        rc, _, err = _ssh(ip, cmd, timeout=10)
        if rc == 0:
            out.append(f"{ip}: OS shutdown issued")
        elif rc == 255:
            out.append(f"{ip}: unreachable (already down?)")
        else:
            out.append(f"{ip}: rc={rc} {err.strip()[:80]}")
    out.append("Cluster mode -> maintenance (watchdog stood down).")
    out.append("Physical 5V power is still ON — cut via Sonoff/Alexa if needed.")
    return "\n".join(out)


@mcp.tool()
def power_on_verify(timeout_s: int = 120) -> str:
    """After the Sonoff/Alexa restores 5V, poll all 11 nodes and verify they are
    back. Flips cluster mode back to 'normal' so the watchdog resumes.

    This tool does NOT cut/toggle power (no Sonoff API) — it only verifies the
    voice-triggered power-on succeeded and re-arms the watchdog.
    """
    import socket
    deadline = time.time() + timeout_s
    rows = []
    while time.time() < deadline:
        rows = []
        for name, ip in zip(cfg.NODE_NAMES, cfg.NODE_IPS):
            up = False
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2.0)
                    up = s.connect_ex((ip, cfg.RPC_PORT)) == 0
            except Exception:  # noqa: BLE001
                up = False
            rows.append({"name": name, "ip": ip, "rpc_up": up})
        if all(r["rpc_up"] for r in rows):
            break
        time.sleep(5)
    online = sum(1 for r in rows if r["rpc_up"])
    if online == len(rows):
        cfg.set_cluster_mode(cfg.CLUSTER_MODE_NORMAL)
        return json.dumps({"status": "all_up", "online": online,
                           "total": len(rows), "nodes": rows,
                           "mode": "normal (watchdog re-armed)"}, indent=2)
    return json.dumps({"status": "partial", "online": online,
                       "total": len(rows), "nodes": rows,
                       "mode": "still maintenance (watchdog stood down)"}, indent=2)


# ===========================================================================
# cluster.model.*  — registry + resumable download
# ===========================================================================
@mcp.tool()
def model_list() -> str:
    """List every model in the registry with local path, kind, and whether it fits
    the PC headroom without node sharding."""
    out = {}
    for k, v in cfg.MODELS.items():
        out[k] = {
            "local": v["local"],
            "kind": v["kind"],
            "fits_pc": v["fits_pc"],
            "present": os.path.exists(v["local"]),
            "notes": v["notes"],
        }
    return json.dumps(out, indent=2)


@mcp.tool()
def model_download(model_key: str, segments: int = 8, stagger: int = 12) -> str:
    """Start a resumable, range-segmented download of a registry model to C:\\Models.
    Mirrors dl_llama_pc.py. Returns the spawned downloader PID/status.

    model_key: e.g. 'codestral-22b-q8_0' (the one you are fetching now) or
               'deepseek-coder-v2-lite-q4_k_m' (Tier 2 ring target).
    """
    m = cfg.model_entry(model_key)
    out_path = m["local"]
    os.makedirs(cfg.MODELS_DIR, exist_ok=True)
    # The generic downloader takes the registry URL + output directly. Both come from
    # the single source of truth (cluster_config.MODELS), so there is no duplication.
    generic = os.path.join(cfg.CODE_DIR, "dl_generic_model.py")
    if not os.path.exists(generic):
        return f"ERROR: generic downloader missing: {generic}"
    args = [sys.executable, generic, "--url", m["hf_url"],
            "--out", out_path, "--segments", str(segments),
            "--stagger", str(stagger)]
    try:
        p = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return json.dumps({"started": True, "pid": p.pid, "model": model_key,
                           "out": out_path}, indent=2)
    except Exception as e:  # noqa: BLE001
        return f"ERROR launching downloader: {e}"


# ===========================================================================
# ASYNC DISTRIBUTION PRIMITIVES (PC orchestrator side)
# ===========================================================================
def _tcp_up(ip: str, port: int, timeout: float = 2.0) -> bool:
    import socket
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((ip, port)) == 0
    except Exception:  # noqa: BLE001
        return False


async def _gemm_distribute(targets, shards_arr):
    """Stream each shard to a node's GEMM worker, await float16 result, reassemble."""
    import struct
    import numpy as np

    async def send_one(ip, seq_id, shard):
        rows, cols = shard.shape
        payload = shard.tobytes()
        header = struct.pack("!III", seq_id, rows, cols) + b"\x00\x00\x00\x00"
        try:
            reader, writer = await asyncio.open_connection(ip, cfg.GEMM_PORT)
            writer.write(header + payload)
            await writer.drain()
            resp = await reader.readexactly(8)
            ret_seq, nbytes = struct.unpack("!II", resp)
            data = await reader.readexactly(nbytes)
            writer.close()
            await writer.wait_closed()
            return ret_seq, np.frombuffer(data, dtype=np.float16).reshape(rows, rows)
        except Exception as e:  # noqa: BLE001
            print(f"[gemm] node {ip} failed: {e}")
            return seq_id, None

    sem = asyncio.Semaphore(cfg.MAX_CONCURRENT_NET_STREAMS)
    async def throttled(ip, sid, sh):
        async with sem:
            return await send_one(ip, sid, sh)
    tasks = [throttled(ip, i, shards_arr[i]) for i, ip in enumerate(targets)]
    results = await asyncio.gather(*tasks)
    results.sort(key=lambda x: x[0])
    if any(s is None for _, s in results):
        return None
    return np.concatenate([s for _, s in results], axis=0)


async def _embed_distribute(targets, corpus):
    """Round-robin token shards to embedding workers, throttled, reassemble."""
    import struct
    import numpy as np

    async def send_one(ip, seq_id, token_shard):
        num = len(token_shard)
        payload = token_shard.tobytes()
        # Doc wire format: 12-byte header = !II (seq, num_tokens) + 4 padding bytes.
        header = struct.pack("!II", seq_id, num).ljust(12, b"\x00")
        try:
            reader, writer = await asyncio.open_connection(ip, cfg.EMBED_PORT)
            writer.write(header + payload)
            await writer.drain()
            resp = await reader.readexactly(8)
            ret_seq, nbytes = struct.unpack("!II", resp)
            data = await reader.readexactly(nbytes)
            writer.close()
            await writer.wait_closed()
            return ret_seq, np.frombuffer(data, dtype=np.float16).reshape(num, cfg.EMBEDDING_DIM)
        except Exception as e:  # noqa: BLE001
            print(f"[embed] node {ip} failed: {e}")
            return seq_id, None

    sem = asyncio.Semaphore(cfg.MAX_CONCURRENT_NET_STREAMS)
    async def throttled(ip, sid, sh):
        async with sem:
            return await send_one(ip, sid, sh)
    tasks = []
    for idx in range(len(corpus)):
        ip = targets[idx % len(targets)]
        tasks.append(throttled(ip, idx, corpus[idx]))
    results = await asyncio.gather(*tasks)
    results.sort(key=lambda x: x[0])
    valid = [m for _, m in results if m is not None]
    if not valid:
        return None
    return np.vstack(valid)


async def _ring_pump(head_ip, batches):
    """Pump N batches into the ring head; each returns a final hidden-state tensor.
    Transport-only validation (kernel is research-grade)."""
    import struct
    import numpy as np
    ok = True
    num_floats = cfg.RING_BATCH_SIZE * cfg.RING_SEQUENCE_LEN * cfg.RING_HIDDEN_DIM
    payload = np.zeros((cfg.RING_BATCH_SIZE, cfg.RING_SEQUENCE_LEN, cfg.RING_HIDDEN_DIM),
                       dtype=np.float32).tobytes()
    for b in range(batches):
        try:
            reader, writer = await asyncio.open_connection(head_ip, cfg.RING_PORT)
            # Doc wire format: 8-byte header = !II (batch_id, num_floats) + payload.
            hdr = struct.pack("!II", b, num_floats)
            writer.write(hdr + payload)
            await writer.drain()
            resp = await reader.readexactly(8)
            _bid, nbytes = struct.unpack("!II", resp)
            await reader.readexactly(nbytes)
            writer.close()
            await writer.wait_closed()
        except Exception as e:  # noqa: BLE001
            print(f"[ring] batch {b} failed: {e}")
            ok = False
    return ok


# ===========================================================================
# cluster.method.*  — Anti-Dark Forest simulation harnesses as agent tools
# ---------------------------------------------------------------------------
# The 15 pure-numpy method harnesses (../methods/) are the *compute* layer the
# small-model agents use in Stage 2 of the 3-stage meta-loop. Each is exposed as
# a callable tool so an agent can run/iterate it locally on a node
# (compute-to-communication ratio: only the small JSON result crosses the 1GbE
# link, not the simulation work).
#
# Method registry is the single source of truth — mirrors methods/harness.py
# METHODS so the agent-facing list never drifts from the harness code.
# ===========================================================================
METHODS = {
    # --- Phase 1 (Track-3 core) ---
    "marl":       "Asymmetric MARL: EROI of kinetic strike vs mass assimilation.",
    "montecarlo": "Monte Carlo cosmic ergodicity: is Heuristic Seeding a prerequisite?",
    "thermo_ca":  "Thermo CA: Dark Forest strikes as a thermal visibility filter.",
    "kl_div":     "KL-div: simulate bio-chaos vs harvest it natively.",
    "lean":       "Lean dynamics: warfare as Muda, phased out by assimilation.",
    "bayesian":   "Bayesian game theory: blindness (preempt) vs transparency (absorb).",
    # --- Phase 2 (new) ---
    "viability_kernel":    "Viability Kernel: is viable state space sparse & low-dimensional?",
    "replication_thermo":  "Stochastic-thermo replication: does heat respect England's bound?",
    "tiep_lifetime":       "TIEP: does life maximize integrated entropy, not peak rate?",
    "jevons_throughput":   "Jevons: does efficiency selection raise total power throughput?",
    "recursive_viability": "Recursive Viability: does identity I(t)=H-PD(t) converge to 0?",
    # --- Phase 1 (extended) ---
    "cna":                "Complex Network Analysis: information spread through civilisation networks under Dark Forest vs assimilation vs seeding.",
    "tech_diffusion":     "Technology Diffusion: rate of technological advancement under Dark Forest vs assimilation vs seeding.",
    "population_dynamics":"Population Dynamics: long-term viability of seeding vs exploitation vs assimilation across generations.",
    "complex_adaptive":   "Complex Adaptive Systems: knowledge evolution under Dark Forest vs assimilation vs seeding.",
}


@mcp.tool()
def method_list() -> str:
    """List all 15 Anti-Dark Forest simulation methods available as agent tools.

    Returns method key + one-line purpose. Use method_run to execute any of them
    (locally on the PC, or on a node via node_ip)."""
    return json.dumps({"methods": METHODS}, indent=2)


def _parse_overrides(overrides: str) -> dict:
    """Parse 'key=value' pairs into a dict with best-effort numeric coercion."""
    ov = {}
    for item in (overrides or "").split():
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        try:
            v = int(v)
        except ValueError:
            try:
                v = float(v)
            except ValueError:
                pass
        ov[k] = v
    return ov


def _method_run_remote(method: str, node_ip: str, ov_str: str,
                       timeout_s: int) -> str:
    """Run a method on a node via SSH; only the JSON result crosses the wire."""
    cmd = (f"cd {cfg.REMOTE_METHODS_DIR} && "
           f"python3 harness.py {method} --json {ov_str}")
    rc, out, err = _ssh(node_ip, cmd, timeout=timeout_s)
    if rc != 0:
        return json.dumps({"error": "remote run failed", "rc": rc,
                           "stderr": err.strip()[:500]}, indent=2)
    return out.strip()


def _method_run_local(method: str, ov: dict) -> str:
    """Run a method on the PC by importing the harness directly."""
    here = os.path.dirname(os.path.abspath(__file__))
    methods_dir = os.path.join(os.path.dirname(here), "methods")
    if methods_dir not in sys.path:
        sys.path.insert(0, methods_dir)
    try:
        import harness
        result = harness.run_method(method, ov)
        return json.dumps(result, indent=2)
    except Exception as e:  # noqa: BLE001
        return json.dumps({"error": str(e)}, indent=2)


@mcp.tool()
def method_run(method: str, node_ip: str = "", overrides: str = "",
               timeout_s: int = 120) -> str:
    """Run an Anti-Dark Forest simulation method and return its JSON result.

    method: one of marl | montecarlo | thermo_ca | kl_div | lean | bayesian |
             viability_kernel | replication_thermo | tiep_lifetime |
             jevons_throughput | recursive_viability | cna | tech_diffusion |
             population_dynamics | complex_adaptive
    node_ip: if set, run on that node via SSH (compute stays on-node; only the
             JSON result crosses the wire). If empty, run locally on the PC.
    overrides: optional 'key=value' pairs separated by spaces (e.g.
               'steps=1000 agents=200 seed=7') to sweep method parameters.
    timeout_s: hard cap on execution time.

    Returns the method's result dict as JSON. This is the tool a small-model
    agent calls in Stage 2 to execute its assigned methodology per the big
    model's strategy (e.g. Lean = Method 5, cosmic supply-chain optimisation)."""
    if method not in METHODS:
        return json.dumps({"error": f"unknown method '{method}'",
                           "known": list(METHODS)}, indent=2)
    ov = _parse_overrides(overrides)
    ov_str = " ".join(f"{k}={v}" for k, v in ov.items())
    if node_ip:
        return _method_run_remote(method, node_ip, ov_str, timeout_s)
    return _method_run_local(method, ov)


@mcp.tool()
def method_push() -> str:
    """SCP the ../methods/ harness directory to every node (REMOTE_METHODS_DIR)
    so agents can run simulations locally on-node. Idempotent — safe to re-run."""
    src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "methods")
    if not os.path.isdir(src):
        return f"ERROR: methods dir missing: {src}"
    out = []
    for ip in cfg.NODE_IPS:
        rc, _, e = _push(ip, src, cfg.REMOTE_METHODS_DIR + "/", timeout=60)
        out.append(f"{ip}: rc={rc} {'ok' if rc == 0 else e.strip()[:80]}")
    return "\n".join(out)


if __name__ == "__main__":
    mcp.run()
