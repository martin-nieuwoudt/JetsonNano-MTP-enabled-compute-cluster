#!/usr/bin/env python3
r"""
cluster_infer.py — CANONICAL agent entry point for the Jetson Nano RPC cluster
=============================================================================
This is the ONLY script an agent (GitHub Copilot, etc.) should call to run
inference. It hides every old-commit-specific flag quirk of llama.cpp
`b56f079e2` so the agent never has to guess syntax.

WHY THIS EXISTS
---------------
The pinned commit `b56f079e2` (2025-01-04) predates many modern llama.cpp
flags. An agent that "knows" current llama.cpp will use WRONG syntax and fail:
  - Binary is `llama-cli.exe` (RPC *client*), NOT `llama-server` / `llama-rpc-server`.
  - `--rpc SERVERS` is comma-separated host:port (no spaces).
  - Flash attention flag is `--flash-attn` (short `-fa`), NOT `--flash-attn` variants.
  - Conversation mode is `-cnv` / `--conversation`. There is NO `-no-cnv` flag.
  - `--mlock` EXISTS on the client (keeps model in RAM); it does NOT exist on the
    Nano `rpc-server` (that daemon takes only `-H/-p/-m`).
  - Prediction length is `-n` / `--predict` / `--n-predict`.
  - Context size is `-c` / `--ctx-size`.
  - Prompt is `-p` / `--prompt`. Model is `-m` / `--model`.
  - `--no-display-prompt` suppresses the echoed prompt so stdout = pure generation.

USAGE (agent-facing — copy these verbatim)
------------------------------------------
  # Single node (node0 — default target; the full 11-node fleet is proven, see Phase 1):
  python code\cluster_infer.py --prompt "Explain Maxwell's equations simply."

  # Full 11-node cluster (once fleet is flashed — Phases 9a-9d):
  python code\cluster_infer.py --nodes all --prompt "..." --model C:\Models\Qwen2.5-72B-Instruct-IQ3_XS.gguf

  # Machine-readable output for an agent to parse:
  python code\cluster_infer.py --prompt "..." --json

  # Also publish live tok/s to the dashboard (rpc_metrics.json):
  python code\cluster_infer.py --prompt "..." --publish

Requires: the rpc-server daemon running on the target node(s) (Phase 7 / A.4).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

# Force UTF-8 stdout/stderr so model output containing non-cp1252 chars
# (em-dash, smart quotes, unicode) never crashes print() on the Windows
# console. Reconfigure is available on Python 3.7+; fall back silently.
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))


def resolve_cli(build_name):
    """Pick the llama-cli.exe for the requested build variant (single source of truth)."""
    variant = BUILD_VARIANTS.get(build_name, BUILD_VARIANTS[DEFAULT_BUILD])
    return variant["cli"]

# QoS / integrity layer (pre-flight hash, golden-prompt check, retry/health).
# Imported lazily so a missing dependency never blocks a plain inference run.
try:
    import cluster_qos as qos
    QOS_AVAILABLE = True
except Exception as _qos_imp_err:  # pragma: no cover
    qos = None
    QOS_AVAILABLE = False
    print(f"[QOS] module unavailable ({_qos_imp_err}); QoS checks disabled",
          file=sys.stderr)

# SSD weight prewarm (Phase H-A): force each worker's OS page cache to hold the
# model shard before inference so the RPC weight-upload reads from RAM, not the
# SSD over NFS. Imported lazily so a missing module never blocks a plain run.
try:
    import prewarm_nfs as prewarm
    PREWARM_AVAILABLE = True
except Exception as _prewarm_imp_err:  # pragma: no cover
    prewarm = None
    PREWARM_AVAILABLE = False
    print(f"[PREWARM] module unavailable ({_prewarm_imp_err}); prewarm skipped",
          file=sys.stderr)

# Single source of truth for node/port/model config is mcp/cluster_config.py.
# Import it when available; fall back to local copies otherwise.
try:
    import mcp.cluster_config as cfg
    NODE_IPS = cfg.NODE_IPS
    DEFAULT_NODE = cfg.NODE0_IP
    TENSOR_SPLIT_DEFAULT = cfg.TENSOR_SPLIT_DEFAULT
    BUILD_VARIANTS = cfg.BUILD_VARIANTS
    DEFAULT_BUILD = cfg.DEFAULT_BUILD
    RPC_PORT = cfg.RPC_PORT
    STAGE_NODES_AT_ONCE = cfg.STAGE_NODES_AT_ONCE
    STAGE_SETTLE_S = cfg.STAGE_SETTLE_S
except Exception:
    NODE_IPS = [f"192.168.50.{i}" for i in range(150, 161)]
    DEFAULT_NODE = "192.168.50.150"          # default single-node target; full 11-node fleet proven in Phase 1
    TENSOR_SPLIT_DEFAULT = "1,1,1,1,1,1,1,1,1,1,1"
    BUILD_VARIANTS = {"stable": {"cli": r"C:\llama.cpp\build\bin\llama-cli.exe"}}
    DEFAULT_BUILD = "stable"

DEFAULT_MODEL = r"C:\Models\tiny_test\qwen0.5b-q4km.gguf"
METRICS_FILE = os.path.join(HERE, "rpc_metrics.json")

# llama.cpp prints tok/s to stderr in two known formats across builds:
#   stable (b56f079e2):  "eval time = ... ms / N tokens (X.XX tokens per second)"
#   mtp     (b9886)    :  "[ Prompt: 59.9 t/s | Generation: 19.8 t/s ]"
# Prefer the Generation rate (the actual decode speed the UI should show).
TOK_RE = re.compile(r"Generation:\s*([\d.]+)\s*t/s", re.IGNORECASE)
TOK_RE_LEGACY = re.compile(r"([\d.]+)\s*tokens per second", re.IGNORECASE)


def build_rpc_list(nodes_arg):
    """Resolve --nodes into a comma-separated RPC server list."""
    if nodes_arg == "all":
        return ",".join(f"{ip}:50052" for ip in NODE_IPS)
    if "," in nodes_arg:  # already a comma list of IPs or host:port
        parts = [p.strip() for p in nodes_arg.split(",") if p.strip()]
        out = []
        for p in parts:
            out.append(p if ":50052" in p else f"{p}:50052")
        return ",".join(out)
    # single IP (always append :50052; harmless if already present)
    return f"{nodes_arg}:50052"


def build_rpc_list_staged(nodes_arg, at_once=None, settle_s=None):
    """Sequential-staging variant of build_rpc_list (anti-incast, Phase 12).

    Instead of handing llama.cpp ALL nodes at once (which triggers the
    simultaneous 11-connection weight-upload burst that knocked the small
    interconnect switch over on 2026-07-14), we bring nodes online a few at a
    time. We return the FULL list (llama.cpp still needs every server named for
    the tensor split), but we PRE-WARM each stage's connections with a short
    settle delay so the upload burst is spread out instead of simultaneous.

    The pre-warm opens a TCP connect to each staged node's RPC port and leaves
    it (the OS keeps the connection in TIME_WAIT / ESTABLISHED briefly), which
    paces llama.cpp's actual weight push. Tunables come from cluster_config.
    """
    import socket
    at_once = at_once if at_once is not None else STAGE_NODES_AT_ONCE
    settle_s = settle_s if settle_s is not None else STAGE_SETTLE_S
    if nodes_arg == "all":
        ips = list(NODE_IPS)
    elif "," in nodes_arg:
        ips = [p.strip() for p in nodes_arg.split(",") if p.strip()]
    else:
        ips = [nodes_arg]
    # Pre-warm in stages: connect to a slice, then settle so the burst drains.
    for i in range(0, len(ips), max(1, at_once)):
        stage = ips[i:i + max(1, at_once)]
        for ip in stage:
            host = ip.split(":")[0]
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(2.0)
                    s.connect((host, RPC_PORT))
            except Exception:
                pass  # daemon may not be up yet; llama.cpp will surface it
        if i + max(1, at_once) < len(ips):
            time.sleep(settle_s)
    # Return the full comma list (tensor split needs every server named).
    return ",".join(f"{ip}:50052" if ":50052" not in ip else ip for ip in ips)


def guard_model_fits_weakest_node(model_path):
    """OOM guard (Phase 12): refuse to launch if a model's per-node shard
    estimate would exceed the weakest node's available RAM headroom.

    The Jetson Nano is UMA (CPU+GPU share 4 GB). During model load, llama.cpp
    pushes each node's weight shard + overhead into RAM. On 2026-07-14 the BF16
    9B model (~1.52 GB shard + ~0.24 GB overhead) OOM-killed node160. We
    estimate per-node bytes = model_size / SHARD_COUNT * (1 + OVERHEAD_FRAC)
    and compare against OOM_GUARD_WEAKEST_HEADROOM_FRAC * MemAvailable on the
    weakest node. Returns None to proceed, or an int exit code to abort.
    """
    try:
        import mcp.cluster_config as _cfg
        frac = _cfg.OOM_GUARD_WEAKEST_HEADROOM_FRAC
        ovh = _cfg.OOM_GUARD_OVERHEAD_FRAC
        shards = _cfg.SHARD_COUNT
    except Exception:
        return None  # config unavailable -> skip guard, don't block
    if not os.path.exists(model_path):
        return None  # missing file -> let llama.cpp report it
    try:
        size = os.path.getsize(model_path)
    except OSError:
        return None
    per_node = (size / shards) * (1.0 + ovh)
    # Static weakest-node floor (GB): node160 MemAvailable observed 2026-07-14.
    # Conservative so the guard never needs SSH at launch time.
    WEAKEST_MEMAVAIL_GB = 3.47
    weakest_kb = WEAKEST_MEMAVAIL_GB * 1024 * 1024
    ceiling = frac * weakest_kb * 1024  # bytes
    if per_node > ceiling:
        msg = (f"[OOM-GUARD] model {os.path.basename(model_path)} needs "
               f"~{per_node/1024/1024:.0f} MB/node (shard+{int(ovh*100)}% UMA "
               f"overhead) but weakest node headroom ceiling is "
               f"~{ceiling/1024/1024:.0f} MB. ABORTING to prevent OOM kill "
               f"(see 2026-07-14 node160 incident). Use a smaller quant.")
        print(msg, file=sys.stderr)
        return 4
    return None


def build_cmd(args, rpc, cli):
    """Construct the llama-cli command for the selected build. Do NOT "modernize" these flags."""
    cmd = [
        cli,
        "-m", args.model,
        "-p", args.prompt,
        "-n", str(args.tokens),
        "-c", str(args.ctx_size),
        "--rpc", rpc,
        "--no-display-prompt",   # stdout = pure generation (easier for agents to parse)
        "--temp", str(args.temp),
        "--repeat-penalty", str(args.repeat_penalty),
    ]
    # --single-turn only exists in MTP builds (20a04b2+); stable build rejects it
    if args.build == "mtp":
        cmd.append("--single-turn")
    if args.flash_attn:
        cmd.append("--flash-attn")   # short form is -fa; both valid at this commit
    if args.mlock:
        cmd.append("--mlock")        # valid on the CLIENT only (not on rpc-server)
    if args.tensor_split:
        # Even 11-way split: all values equal (relative weights), so every node
        # (node0 first, then .151-.160) carries the same share of the tensors.
        # 11 values map 1:1 to the --rpc servers in order. Overrides the default.
        cmd += ["--tensor-split", args.tensor_split]
    if args.system_file:
        # MTP build (b9886) uses --system-prompt-file (-sysf) to load the
        # model's system prompt from a file. This is the Qwythos system prompt
        # (System Prompt.md), NOT agent operating instructions.
        cmd += ["--system-prompt-file", args.system_file]
    return cmd


def write_metrics(tokens_sec, running, note=""):
    # Preserve last-known non-zero tok/s so the dashboard never goes blind.
    # On "done", if tokens_sec is 0, re-read the previous value.
    if note == "done" and (tokens_sec is None or tokens_sec == 0):
        try:
            with open(METRICS_FILE, "r", encoding="utf-8") as fh:
                prev = json.load(fh)
            tokens_sec = prev.get("tokens_sec", 0.0)
        except Exception:
            pass
    data = {"tokens_sec": tokens_sec, "kv_cells": "n/a",
            "running": running, "updated": time.time(), "note": note}
    tmp = METRICS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(tmp, METRICS_FILE)


def run_qos_guards(args):
    """Run the cheap pre-flight integrity checks. Returns None to proceed,
    or an int exit code to abort the run."""
    if not (QOS_AVAILABLE and not args.no_qos):
        return None
    try:
        # #1 pre-flight: sha256 the GGUF on the PC (the authoritative model
        # store). All orchestration is PC-side; the PC pushes every shard over
        # RPC, so the PC file IS the source of truth. Pass the real PC path.
        qos.preflight_model_hash(args.model)
        # #3 golden-prompt determinism check (skipped unless --qos-golden is
        #    passed, to avoid an extra inference on normal runs).
        if args.qos_golden:
            ok, _, _ = qos.golden_prompt_check(args.model, nodes=args.nodes)
            if not ok:
                print("[QOS#3] golden-prompt MISMATCH — aborting run.",
                      file=sys.stderr)
                return 1
    except qos.QosError as e:
        print(str(e), file=sys.stderr)
        return 3
    return None


def run(args):
    # --- OOM GUARD (Phase 12): abort before a too-large model OOM-kills the
    # weakest node (the 2026-07-14 node160 incident). Skippable with --no-qos.
    if not args.no_qos:
        oom_guard = guard_model_fits_weakest_node(args.model)
        if oom_guard is not None:
            if args.publish:
                write_metrics(0.0, False, note="oom-guard abort")
            if args.json:
                print(json.dumps({"ok": False, "error": "oom-guard abort"}))
            return oom_guard

    # --- SSD WEIGHT PREWARM (Phase H-A): RETIRED 2026-07-15.
    # The node0 SSD was removed and reformatted as a local PC drive (D:), and the
    # Nano nodes are dumb weight *receivers* that never load from disk — the PC
    # pushes every shard over RPC on each run. The prewarm cached the model into
    # node0's SSD page cache over NFS, which no longer exists, so this step is
    # dead. Disabled. (prewarm_nfs module left in place but no longer called.)
    if False and PREWARM_AVAILABLE and not args.no_prewarm:
        try:
            prewarm.prewarm_all(args.model, ips=NODE_IPS if args.nodes == "all"
                                else [p.strip() for p in args.nodes.split(",")
                                      if p.strip()])
        except Exception as _pw_err:  # pragma: no cover
            print(f"[PREWARM] prewarm error ({_pw_err}); continuing without it",
                  file=sys.stderr)

    # --- ANTI-INCAST STAGED CONNECT (Phase 12): pre-warm nodes a few at a
    # time so the weight-upload burst is spread out instead of simultaneous.
    # Falls back to the plain list when --no-qos is set (no pacing).
    if args.no_qos:
        rpc = build_rpc_list(args.nodes)
    else:
        rpc = build_rpc_list_staged(args.nodes)
    cli = resolve_cli(args.build)
    cmd = build_cmd(args, rpc, cli)

    # --- QoS / integrity guards (cheap, no measurable time-to-answer hit) ---
    guard = run_qos_guards(args)
    if guard is not None:
        return guard

    if args.verbose or args.json is False:
        print(f"[INFER] exact command:\n  {' '.join(cmd)}\n", file=sys.stderr)

    if not os.path.exists(cli):
        msg = f"llama-cli.exe not found at {cli}"
        print(msg, file=sys.stderr)
        if args.publish:
            write_metrics(0.0, False, note="cli missing")
        if args.json:
            print(json.dumps({"ok": False, "error": msg}))
        return 2

    if args.publish:
        write_metrics(0.0, True, note="running")

    def _run_exec():
        p = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1, encoding="utf-8", errors="replace",
        )
        gen_parts = []
        tok = None
        # Stream stderr live so the dashboard shows real-time tok/s instead of
        # sitting on a stale "running/0.0" for the whole run.
        for line in p.stderr:
            if args.verbose or args.json is False:
                sys.stderr.write(line)
            m = TOK_RE.search(line) or TOK_RE_LEGACY.search(line)
            if m:
                tok = float(m.group(1))
                if args.publish:
                    write_metrics(tok, True, note="running")
        # stdout = pure generation (--no-display-prompt)
        for chunk in p.stdout:
            gen_parts.append(chunk)
        p.wait()
        if args.publish:
            write_metrics(tok or 0.0, True, note="done")
        return {
            "ok": p.returncode == 0,
            "returncode": p.returncode,
            "prompt": args.prompt,
            "model": args.model,
            "rpc": rpc,
            "tokens_per_second": tok,
            "generation": "".join(gen_parts).strip(),
            "command": " ".join(cmd),
        }

    # #4 resilience: retry + relaunch a dropped RPC daemon (no throttling).
    if QOS_AVAILABLE and not args.no_qos:
        result = qos.run_with_retry(_run_exec)
    else:
        result = _run_exec()

    if args.json:
        # Write via UTF-8 buffer: the model output may contain non-cp1252
        # chars (em-dash, smart quotes) that crash a raw print() on the
        # Windows console (the 2026-07-14 Phase-1 crash, both json + text
        # branches).
        try:
            sys.stdout.buffer.write(
                (json.dumps(result, ensure_ascii=False) + "\n").encode("utf-8"))
        except Exception:
            print(json.dumps(result, ensure_ascii=True))
    else:
        tok = result.get("tokens_per_second")
        print("=" * 60)
        print("PROMPT :", args.prompt)
        print("RPC    :", rpc)
        print("SPEED  :", f"{tok:.2f} tok/s" if tok is not None else "n/a")
        print("-" * 60)
        # Model output may contain non-cp1252 chars (em-dash, smart quotes,
        # unicode). Print via UTF-8 re-encode to avoid UnicodeEncodeError on
        # the Windows console (the 2026-07-14 Phase-1 crash).
        try:
            sys.stdout.buffer.write((result["generation"] + "\n").encode("utf-8"))
        except Exception:
            print(result["generation"])
        print("=" * 60)
    return 0 if result["ok"] else 1


def main():
    ap = argparse.ArgumentParser(
        description="Canonical RPC inference wrapper for the Jetson Nano cluster (llama.cpp b56f079e2).")
    ap.add_argument("--prompt", required=True, help="prompt text to generate from")
    ap.add_argument("--model", default=DEFAULT_MODEL, help="GGUF model path")
    ap.add_argument("--nodes", default=DEFAULT_NODE,
                    help="single IP, comma list, or 'all' for the 11-node fleet")
    ap.add_argument("--tokens", type=int, default=128, help="tokens to predict (-n)")
    ap.add_argument("--ctx-size", type=int, default=4096, help="context size (-c)")
    ap.add_argument("--temp", type=float, default=0.8, help="temperature")
    ap.add_argument("--repeat-penalty", type=float, default=1.0, help="repeat penalty")
    ap.add_argument("--flash-attn", action="store_true", help="enable Flash Attention")
    ap.add_argument("--mlock", action="store_true", help="keep model in RAM (client only)")
    ap.add_argument("--tensor-split", default=TENSOR_SPLIT_DEFAULT,
                    help="per-node layer share (11 values, node0 first); caps node0 headroom")
    ap.add_argument("--publish", action="store_true", help="write rpc_metrics.json for dashboard")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    ap.add_argument("--verbose", action="store_true", help="print the exact command")
    ap.add_argument("--build", default=DEFAULT_BUILD, choices=list(BUILD_VARIANTS),
                    help="llama.cpp build variant: stable (default) or mtp (multi-token prediction)")
    ap.add_argument("--no-qos", action="store_true",
                    help="skip QoS guards (pre-flight hash, golden check, retry)")
    ap.add_argument("--no-prewarm", action="store_true",
                    help="skip SSD weight prewarm (Phase H-A) before inference")
    ap.add_argument("--system-file", default=None,
                    help="path to a system-prompt file (MTP: --system-prompt-file)")
    ap.add_argument("--qos-golden", action="store_true",
                    help="also run the golden-prompt determinism check before launch")
    args = ap.parse_args()
    sys.exit(run(args))


if __name__ == "__main__":
    main()
