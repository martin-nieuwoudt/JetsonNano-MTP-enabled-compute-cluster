#!/usr/bin/env bash
for n in 150 155 159; do
  ip="192.168.50.$n"
  echo "===== $ip ====="
  timeout 8 ssh -o BatchMode=yes jetson@$ip 'echo "--- build info (rpc-server) ---"; strings /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server 2>/dev/null | grep -iE "commit|20a04b|build" | head -3; echo "--- source tree present? ---"; ls /home/jetson/llama.cpp-mtp/CMakeLists.txt 2>&1; echo "--- git dir? ---"; ls -d /home/jetson/llama.cpp-mtp/.git 2>&1' 2>/dev/null
done
