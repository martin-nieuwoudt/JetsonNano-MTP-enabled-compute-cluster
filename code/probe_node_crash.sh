#!/usr/bin/env bash
for i in 151 152 156 160; do
  echo "===== node $i ====="
  ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no jetson@192.168.50.$i '
    echo "--- free -m ---"; free -m | head -3
    echo "--- dmesg OOM/error ---"; dmesg -T 2>/dev/null | grep -iE "oom|killed process|out of memory|segfault|rpc" | tail -8
    echo "--- ggml-rpc-server procs ---"; pgrep -a ggml-rpc-server || echo NONE
  ' 2>&1
done
