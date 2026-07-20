#!/usr/bin/env bash
# Compare free memory + UMA across all 11 nodes right now
for i in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$i"
  out=$(ssh -o BatchMode=yes "jetson@$ip" 'free -m | awk "NR==2{print \$7}"; sudo journalctl -u llama-rpc.service -n 3 --no-pager 2>/dev/null | grep -o "available_memory_kb: [0-9]*" | tail -1')
  echo "$ip -> availMB=$(echo "$out" | head -1)  uma=$(echo "$out" | tail -1)"
done
