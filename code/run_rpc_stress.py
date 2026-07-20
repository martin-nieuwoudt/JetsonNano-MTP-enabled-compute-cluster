#!/usr/bin/env python3
"""
run_rpc_stress.py — RPC inference stress runner + live metrics publisher
========================================================================
Launches llama-cli.exe (the CPU-only RPC client) against the Jetson
rpc-server(s) and publishes the measured tok/s to rpc_metrics.json, which
cluster_telemetry.py reads to drive the dashboard's "Gen Speed" card.

This is the piece that makes the dashboard reflect REAL inference speed during
a stress test. The old dashboard scraped :8080 (a llama-server HTTP endpoint)
which does not exist in this RPC-client setup, so Gen Speed was always blind.

Usage:
  python run_rpc_stress.py
  python run_rpc_stress.py --model C:\Models\tiny_test\qwen0.5b-q4km.gguf --rpc 192.168.50.150:50052 --prompt "Hello" --tokens 64 --loop
  python run_rpc_stress.py --rpc 192.168.50.150:50052,192.168.50.151:50052 --loop

Requires: the rpc-server daemon running on the target node(s).
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
CLI = r"C:\llama.cpp\build\bin\llama-cli.exe"
METRICS_FILE = os.path.join(HERE, "rpc_metrics.json")
# llama.cpp prints "eval time = ... ms / N tokens (X.XX tokens per second)" to stderr.
TOK_RE = re.compile(r"([\d.]+)\s*tokens per second", re.IGNORECASE)


def write_metrics(tokens_sec, kv_cells, running, note=""):
    """Atomically publish metrics so the dashboard never reads a partial file."""
    data = {
        "tokens_sec": tokens_sec,
        "kv_cells": kv_cells,
        "running": running,
        "updated": time.time(),
        "note": note,
    }
    tmp = METRICS_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    os.replace(tmp, METRICS_FILE)


def run_once(cli, model, rpc, prompt, tokens, flash_attn):
    cmd = [cli, "-m", model, "-p", prompt, "-n", str(tokens), "--rpc", rpc]
    if flash_attn:
        cmd.append("--flash-attn")
    # llama-cli prints timing to stderr; merge streams so we capture it all.
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, encoding="utf-8", errors="replace",
    )
    last_tok = 0.0
    kv = "n/a"
    for line in proc.stdout:
        sys.stdout.write(line)
        m = TOK_RE.search(line)
        if m:
            last_tok = float(m.group(1))
    proc.wait()
    return last_tok, kv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cli", default=CLI)
    ap.add_argument("--model", default=r"C:\Models\tiny_test\qwen0.5b-q4km.gguf")
    ap.add_argument("--rpc", default="192.168.50.150:50052")
    ap.add_argument("--prompt", default="Hello")
    ap.add_argument("--tokens", type=int, default=64)
    ap.add_argument("--flash-attn", action="store_true")
    ap.add_argument("--loop", action="store_true", help="repeat until Ctrl+C")
    args = ap.parse_args()

    if not os.path.exists(args.cli):
        print(f"[STRESS] ERROR: llama-cli.exe not found at {args.cli}", file=sys.stderr)
        write_metrics(0.0, "n/a", False, note="cli missing")
        sys.exit(2)

    print(f"[STRESS] target={args.rpc} model={args.model} loop={args.loop}")
    try:
        while True:
            write_metrics(0.0, "n/a", True, note="running")
            tok, kv = run_once(
                args.cli, args.model, args.rpc, args.prompt, args.tokens, args.flash_attn
            )
            write_metrics(tok, kv, True, note="last run done")
            if not args.loop:
                break
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\n[STRESS] stopped.")
    finally:
        write_metrics(0.0, "n/a", False, note="idle")


if __name__ == "__main__":
    main()
