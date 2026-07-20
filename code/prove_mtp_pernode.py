#!/usr/bin/env python3
"""Per-node MTP load+infer proof. Tests each node INDIVIDUALLY (no simultaneous
11-shard allocation) so a client-side incast crash can't mask per-node capability.
The MTP binary is byte-identical fleet-wide (sha256 70848020...0d25c), so a pass
on each node proves the build loads and infers everywhere."""
import json, subprocess, sys
MODEL = r"C:\Models\Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf"
PROMPT = "In one sentence, what is the speed of light?"
NODES = [f"192.168.50.{i}" for i in range(150, 161)]
results = {}
for ip in NODES:
    cmd = [sys.executable, "cluster_infer.py", "--build", "mtp", "--nodes", ip,
           "--model", MODEL, "--prompt", PROMPT, "--tokens", "32",
           "--no-qos", "--json"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=180)
        # last JSON line on stdout
        last = ""
        for line in out.stdout.splitlines():
            line = line.strip()
            if line.startswith("{"):
                last = line
        if last:
            d = json.loads(last)
            gen = d.get("generation", "")
            ok = d.get("ok") and "Loading model" not in gen and len(gen.strip()) > 0
            results[ip] = {"ok": bool(ok), "rc": d.get("returncode"),
                           "gen_head": gen.strip()[:60].replace("\n", " ")}
        else:
            results[ip] = {"ok": False, "rc": out.returncode, "gen_head": out.stderr[-120:]}
    except Exception as e:
        results[ip] = {"ok": False, "rc": -1, "gen_head": str(e)[:120]}
    print(f"{ip}: ok={results[ip]['ok']} rc={results[ip]['rc']} :: {results[ip]['gen_head']}",
          flush=True)
passed = sum(1 for v in results.values() if v["ok"])
print(f"\n===== {passed}/{len(NODES)} nodes load+infer OK =====")
sys.exit(0 if passed == len(NODES) else 1)
