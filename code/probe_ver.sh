#!/usr/bin/env bash
for n in 150 155 159; do
  ip="192.168.50.$n"
  echo "===== $ip ====="
  timeout 8 ssh -o BatchMode=yes jetson@$ip 'echo --- rpc-server binary ---; ls -la /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server; echo --- version string ---; /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server --version 2>&1 | head -3; echo --- git commit ---; cd /home/jetson/llama.cpp-mtp 2>/dev/null && git rev-parse HEAD 2>/dev/null; echo --- rpc log tail ---; sudo journalctl -u llama-rpc.service -n 3 --no-pager 2>/dev/null | tail -3' 2>/dev/null
done
