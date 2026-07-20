#!/bin/bash
for n in 151 152 153; do
  echo "=== node .$n ==="
  ssh -o BatchMode=yes jetson@192.168.50.$n 'bash -s' <<INNER
    echo "-- process --"; pgrep -af ggml-rpc-server || echo "none"
    echo "-- port 50053 --"; (ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null) | grep 50053 || echo "not listening"
    echo "-- log tail --"; tail -n 15 /home/jetson/mtp_rpc_$n.log 2>/dev/null || echo "no log"
INNER
done
