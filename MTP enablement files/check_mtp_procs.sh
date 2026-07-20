#!/usr/bin/env bash
for n in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$n"
  echo "=== $ip ==="
  ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no jetson@$ip \
    'pgrep -af ggml-rpc-server || echo "  no mtp proc"; ls -la /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server 2>&1' 2>&1
done
