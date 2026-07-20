#!/usr/bin/env bash
# Find which node's RPC worker crashed / is down right now
for i in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$i"
  st=$(ssh -o BatchMode=yes -o ConnectTimeout=5 "jetson@$ip" 'pgrep -f ggml-rpc-server >/dev/null && echo UP || echo DOWN' 2>/dev/null || echo UNREACH)
  echo "$ip -> $st"
done
