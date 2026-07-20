#!/usr/bin/env bash
# Scan every node journal for the crash signature from the last load attempt
for i in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$i"
  hit=$(ssh -o BatchMode=yes -o ConnectTimeout=5 "jetson@$ip" 'sudo journalctl -u llama-rpc.service -n 30 --no-pager 2>/dev/null | grep -iE "crash|segfault|abort|signal|oom|cudaMalloc|unknown error" | tail -2' 2>/dev/null || echo UNREACH)
  echo "$ip -> ${hit:-clean}"
done
