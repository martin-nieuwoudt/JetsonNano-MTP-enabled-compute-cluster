#!/usr/bin/env python3
r"""
cluster_server.py — Persistent sharded-inference server for the Jetson cluster
==============================================================================
WHY THIS EXISTS
---------------
cluster_infer.py re-uploads the entire model across all 11 nanos on EVERY
prompt. For an 18 GB Q4_K_M GGUF that is ~18 GB pushed over 1 Gbps each time —
wasteful. llama-server loads the sharded model ONCE and keeps it RESIDENT in
the nanos' UMA RAM, then serves unlimited prompts over HTTP. The shards stay
put until you manually `stop` the server (that is the "manual clear").

This is the canonical way to keep the cluster "warm" between prompts.

USAGE
-----
  python cluster_server.py start  --model C:\Models\Qwen2.5-32B-Instruct-Q4_K_M.gguf [--ctx-size 4096]
  python cluster_server.py stop
  python cluster_server.py status
  python cluster_server.py prompt "What is the capital of France? Answer in one sentence." [--tokens 256]

Requires: the ggml-rpc-server daemons running on all 11 nodes (Phase 7 / A.4).
All changeable facts (paths, ports, node list, tensor split) come from
mcp/cluster_config.py — nothing is hardcoded here.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None

# Local-only HTTP on trusted LAN (loopback/127.0.0.1). No credentials or PII.
# nosec B104: HTTP is intentional for local cluster control plane.
HTTP_LOCAL = True

try:
    import mcp.cluster_config as cfg
    NODE_IPS = cfg.NODE_IPS
    RPC_PORT = cfg.RPC_PORT
    TENSOR_SPLIT_DEFAULT = cfg.TENSOR_SPLIT_DEFAULT
    SERVER_BIN = cfg.SERVER_BIN
    SERVER_HOST = cfg.SERVER_HOST
    SERVER_PORT = cfg.SERVER_PORT
    SERVER_PID_FILE = cfg.SERVER_PID_FILE
    SERVER_LOG = cfg.SERVER_LOG
    SAMPLING_TEMP = cfg.SAMPLING_TEMP
    SAMPLING_MIN_P = cfg.SAMPLING_MIN_P
    SAMPLING_TOP_P = cfg.SAMPLING_TOP_P
    SAMPLING_REPEAT_PENALTY = cfg.SAMPLING_REPEAT_PENALTY
    select_nodes_for_model = cfg.select_nodes_for_model
    partition_ensemble = cfg.partition_ensemble
    ENSEMBLE_EJECT_RESIDENT_FIRST = cfg.ENSEMBLE_EJECT_RESIDENT_FIRST
    SERVER_PORT_POOL = cfg.SERVER_PORT_POOL
except Exception as _e:  # pragma: no cover
    print(f"[SERVER] cluster_config unavailable ({_e}); using built-ins",
          file=sys.stderr)
    NODE_IPS = [f"192.168.50.{i}" for i in range(150, 161)]
    RPC_PORT = 50052
    TENSOR_SPLIT_DEFAULT = "1,1,1,1,1,1,1,1,1,1,1"
    SERVER_BIN = r"C:\llama.cpp\build\bin\llama-server.exe"
    SERVER_HOST = "127.0.0.1"
    SERVER_PORT = 8080
    HERE = os.path.dirname(os.path.abspath(__file__))
    SERVER_PID_FILE = os.path.join(HERE, "cluster_server.pid")
    SERVER_LOG = os.path.join(HERE, "cluster_server.log")
    SAMPLING_TEMP = 0.1
    SAMPLING_MIN_P = 0.05
    SAMPLING_TOP_P = 0.9
    SAMPLING_REPEAT_PENALTY = 1.1
    select_nodes_for_model = None
    partition_ensemble = None
    ENSEMBLE_EJECT_RESIDENT_FIRST = True
    SERVER_PORT_POOL = list(range(8081, 8092))


def _rpc_list():
    return ",".join(f"{ip}:{RPC_PORT}" for ip in NODE_IPS)


def _read_pid():
    try:
        with open(SERVER_PID_FILE, "r", encoding="utf-8") as f:
            return int(f.read().strip())
    except Exception:
        return None


def _is_alive(pid):
    if pid is None:
        return False
    # psutil.pid_exists is cross-platform and reliable. os.kill(pid, 0) on
    # Windows raises WinError 87 ("The parameter is incorrect") for certain
    # live processes instead of a clean "not found", which would wrongly
    # report the server as dead. psutil avoids that pitfall.
    try:
        return psutil.pid_exists(pid)
    except Exception:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def cmd_start(args):
    pid = _read_pid()
    if _is_alive(pid):
        # nosec B104 - local trusted LAN, no credentials/PII
        server_url = f"http://{SERVER_HOST}:{SERVER_PORT}"
        print(f"[SERVER] already running (pid {pid}) on {server_url}")
        return 0
    # Size-based split + random node selection: when the user does not pass an
    # explicit --tensor-split override, pick the minimum node subset that fits
    # the model and choose the nodes at random (node0 included, smaller share).
    if args.tensor_split == TENSOR_SPLIT_DEFAULT and select_nodes_for_model:
        rpc, split = select_nodes_for_model(args.model)
        print(f"[SERVER] size-based split -> {split} across {rpc}", file=sys.stderr)
    else:
        rpc = _rpc_list()
        split = args.tensor_split
    cmd = [
        SERVER_BIN,
        "-m", args.model,
        "--rpc", rpc,
        "--tensor-split", split,
        "--host", SERVER_HOST,
        "--port", str(SERVER_PORT),
        "-c", str(args.ctx_size),
        "--no-warmup",
        "--temp", str(SAMPLING_TEMP),
        "--min-p", str(SAMPLING_MIN_P),
        "--top-p", str(SAMPLING_TOP_P),
        "--repeat-penalty", str(SAMPLING_REPEAT_PENALTY),
    ]
    print(f"[SERVER] launching persistent server (loads shards ONCE into the "
          f"nanos' RAM, then keeps them resident):\n  {' '.join(cmd)}\n",
          file=sys.stderr)
    log = open(SERVER_LOG, "w", encoding="utf-8")
    # DETACHED_PROCESS + CREATE_NEW_PROCESS_GROUP: the server must OUTLIVE the
    # wrapper that launched it. Without this, when the `start` command returns
    # the OS/terminal tears down the whole process tree and kills llama-server
    # (the shards would be freed instantly). Detaching makes it a standalone
    # service that only dies on an explicit `stop`.
    kwargs = {
        "stdout": log,
        "stderr": subprocess.STDOUT,
        "text": True,
        "bufsize": 1,
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)
    p = subprocess.Popen(cmd, **kwargs)
    with open(SERVER_PID_FILE, "w", encoding="utf-8") as f:
        f.write(str(p.pid))
    # Wait for the HTTP endpoint to come up (model load can take ~5s for 32B).
    # nosec B104 - local trusted LAN, no credentials/PII
    wait_url = f"http://{SERVER_HOST}:{SERVER_PORT}"  # nosec B104
    print(f"[SERVER] waiting for {wait_url} "
          f"(loading shards into cluster)...", file=sys.stderr)
    deadline = time.time() + 180
    while time.time() < deadline:
        if not _is_alive(p.pid):
            print(f"[SERVER] process exited early — see {SERVER_LOG}",
                  file=sys.stderr)
            return 1
        try:
            # nosec B104 - local trusted LAN, no credentials/PII
            health_url = f"http://{SERVER_HOST}:{SERVER_PORT}/health"  # nosec B104
            with urllib.request.urlopen(health_url, timeout=2) as r:
                if r.status == 200:
                    # nosec B104 - local trusted LAN, no credentials/PII
                    ready_url = f"http://{SERVER_HOST}:{SERVER_PORT}"  # nosec B104
                    print(f"[SERVER] READY on {ready_url} "
                          f"— shards resident in the nanos. Send prompts with "
                          f"`prompt`. Stop with `stop` to free the RAM.",
                          file=sys.stderr)
                    return 0
        except Exception:
            time.sleep(1.5)
    print(f"[SERVER] timed out waiting for /health — see {SERVER_LOG}",
          file=sys.stderr)
    return 1


def _kill_tree(pid):
    """Terminate a process tree. Windows needs taskkill /T; POSIX uses signals."""
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/F", "/T"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except OSError:
        return
    for _ in range(20):
        if not _is_alive(pid):
            return
        time.sleep(0.5)
    print("[SERVER] did not exit gracefully; sending SIGKILL.", file=sys.stderr)
    try:
        os.kill(pid, signal.SIGKILL)
    except OSError:
        pass


def cmd_stop(args):
    pid = _read_pid()
    alive = _is_alive(pid)
    if alive:
        print(f"[SERVER] stopping pid {pid} — nanos will release their shards.",
              file=sys.stderr)
        _kill_tree(pid)
    else:
        print("[SERVER] not running (or pid file stale).")
    try:
        os.remove(SERVER_PID_FILE)
    except OSError:
        pass
    if alive:
        print("[SERVER] stopped. Shards freed.", file=sys.stderr)
    return 0


def cmd_ensemble_stop(_args):
    state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "ensemble_state.json")
    try:
        with open(state_path, "r", encoding="utf-8") as f:
            state = json.load(f)
    except Exception:
        print("[ENSEMBLE] no ensemble state found.", file=sys.stderr)
        return 0
    stopped_any = False
    for port, pid in state.get("pids", {}).items():
        if _is_alive(int(pid)):
            print(f"[ENSEMBLE] stopping port {port} (pid {pid})...",
                  file=sys.stderr)
            _kill_tree(int(pid))
            stopped_any = True
    try:
        os.remove(state_path)
    except OSError:
        pass
    if stopped_any:
        print("[ENSEMBLE] all ensemble models stopped. Shards freed.", file=sys.stderr)
        return 0
    else:
        print("[ENSEMBLE] no running ensemble models found.", file=sys.stderr)
        return 1


def cmd_status(args):
    pid = _read_pid()
    if not _is_alive(pid):
        print("status: STOPPED (no resident shards)")
        return 0
    try:
        # nosec B104 - local trusted LAN, no credentials/PII
        health_url = f"http://{SERVER_HOST}:{SERVER_PORT}/health"
        with urllib.request.urlopen(health_url, timeout=3) as r:
            body = json.loads(r.read().decode())
        # nosec B104 - local trusted LAN, no credentials/PII
        status_url = f"http://{SERVER_HOST}:{SERVER_PORT}"
        print(f"status: RUNNING (pid {pid}) on {status_url}")
        print(f"health: {json.dumps(body)}")
        return 0
    except Exception as e:
        print(f"status: RUNNING (pid {pid}) but /health unreachable: {e}")
        return 1


def cmd_prompt(args):
    pid = _read_pid()
    if not _is_alive(pid):
        print("[SERVER] not running. Start it first:\n"
              "  python cluster_server.py start --model <GGUF>", file=sys.stderr)
        return 1
    payload = json.dumps({
        "prompt": args.prompt,
        "n_predict": args.tokens,
        "temperature": args.temp,
        "repeat_penalty": args.repeat_penalty,
    }).encode("utf-8")
    # nosec B104 - local trusted LAN, no credentials/PII
    url = f"http://{SERVER_HOST}:{SERVER_PORT}/completion"
    req = urllib.request.Request(url, data=payload,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.loads(r.read().decode())
        content = resp.get("content", "")
        tps = resp.get("timings", {}).get("predicted_per_second")
        print("=" * 60)
        print("PROMPT :", args.prompt)
        print("SPEED  :", f"{tps:.2f} tok/s" if tps else "n/a")
        print("-" * 60)
        try:
            sys.stdout.buffer.write((content + "\n").encode("utf-8"))
        except Exception:
            print(content)
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"[SERVER] prompt failed: {e}", file=sys.stderr)
        return 1


def cmd_ensemble_start(args):
    """Launch N models on disjoint random node subsets as detached, resident
    llama-servers (one per port from SERVER_PORT_POOL). Writes ensemble_state.json
    with the per-member assignment + pid so the dashboard can probe /health and
    stop them later. Sampling/ctx come from the dashboard UI (or config defaults).
    """
    if partition_ensemble is None:
        print("[ENSEMBLE] partition_ensemble unavailable (cluster_config missing).",
              file=sys.stderr)
        return 1
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if not models:
        print("[ENSEMBLE] no models specified.", file=sys.stderr)
        return 1
    try:
        assignments = partition_ensemble(models)
    except ValueError as e:
        print(f"[ENSEMBLE] {e}", file=sys.stderr)
        return 1

    state_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              "ensemble_state.json")
    pids = {}
    launched = []
    for a in assignments:
        cmd = [
            SERVER_BIN,
            "-m", a["model"],
            "--rpc", a["rpc"],
            "--tensor-split", a["split"],
            "--host", SERVER_HOST,
            "--port", str(a["port"]),
            "-c", str(args.ctx_size),
            "--no-warmup",
            "--temp", str(args.temp),
            "--min-p", str(args.min_p),
            "--top-p", str(args.top_p),
            "--repeat-penalty", str(args.repeat_penalty),
        ]
        log = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                f"cluster_server_{a['port']}.log"),
                   "w", encoding="utf-8")
        kwargs = {"stdout": log, "stderr": subprocess.STDOUT, "text": True, "bufsize": 1}
        if sys.platform == "win32":
            kwargs["creationflags"] = (
                subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS)
        p = subprocess.Popen(cmd, **kwargs)
        pids[str(a["port"])] = p.pid
        launched.append({
            "model": a["model"], "port": a["port"], "rpc": a["rpc"],
            "split": a["split"], "nodes": a["nodes"], "pid": p.pid,
        })
        print(f"[ENSEMBLE] launched {os.path.basename(a['model'])} on "
              f"port {a['port']} (pid {p.pid}) -> {a['rpc']}", file=sys.stderr)
    with open(state_path, "w", encoding="utf-8") as f:
        json.dump({"assignments": launched, "pids": pids}, f, indent=2)
    print(f"[ENSEMBLE] {len(launched)} member(s) launched. State: {state_path}",
          file=sys.stderr)
    return 0


def main():
    ap = argparse.ArgumentParser(
        description="Persistent sharded-inference server for the Jetson cluster.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("start", help="load model once, keep shards resident")
    sp.add_argument("--model", required=True, help="GGUF model path")
    sp.add_argument("--ctx-size", type=int, default=16384, help="context size (-c)")
    sp.add_argument("--tensor-split", default=TENSOR_SPLIT_DEFAULT,
                    help="per-node layer share (11 values, node0 first)")
    sp.set_defaults(func=cmd_start)

    sub.add_parser("stop", help="stop server, free nanos' shards").set_defaults(
        func=cmd_stop)
    sub.add_parser("status", help="show running/stopped + health").set_defaults(
        func=cmd_status)

    pp = sub.add_parser("prompt", help="send a prompt WITHOUT reloading the model")
    pp.add_argument("--prompt", required=True, help="prompt text")
    pp.add_argument("--tokens", type=int, default=256, help="max tokens to predict")
    pp.add_argument("--temp", type=float, default=0.8, help="temperature")
    pp.add_argument("--repeat-penalty", type=float, default=1.0,
                    help="repeat penalty")
    pp.set_defaults(func=cmd_prompt)

    es = sub.add_parser("ensemble-start",
                        help="launch N models on disjoint random node subsets")
    es.add_argument("--models", required=True,
                    help="comma-separated GGUF paths (explicit selection)")
    es.add_argument("--ctx-size", type=int, default=2048, help="context size (-c)")
    es.add_argument("--temp", type=float, default=SAMPLING_TEMP, help="temperature")
    es.add_argument("--min-p", type=float, default=SAMPLING_MIN_P, help="min-p")
    es.add_argument("--top-p", type=float, default=SAMPLING_TOP_P, help="top-p")
    es.add_argument("--repeat-penalty", type=float, default=SAMPLING_REPEAT_PENALTY,
                    help="repeat penalty")
    es.set_defaults(func=cmd_ensemble_start)
    sub.add_parser("ensemble-stop",
                   help="stop all ensemble models, free their shards"
                   ).set_defaults(func=cmd_ensemble_stop)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
