#!/usr/bin/env bash
for n in 155 159 160; do
  ip="192.168.50.$n"
  echo "===== $ip ====="
  timeout 8 ssh -o BatchMode=yes jetson@$ip 'cd /home/jetson/llama.cpp-mtp 2>/dev/null && { echo "commit: $(git rev-parse HEAD 2>&1)"; echo "branch: $(git branch --show-current 2>&1)"; echo "status: $(git status -s 2>&1 | head -3)"; } || echo "NO REPO / cd failed"; echo "binary mtime: $(stat -c %y /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server 2>&1)"' 2>/dev/null
done
