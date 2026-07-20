#!/bin/bash
# probe_fleet_rpc.sh - find running rpc-server processes across all 11 nodes
for ip in 150 151 152 153 154 155 156 157 158 159 160; do
  echo "=== node .$ip ==="
  ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=no jetson@192.168.50.$ip bash -s <<'REMOTE' 2>/dev/null || echo "  SSH_FAIL"
ps aux | grep -E "rpc-server|ggml-rpc" | grep -v grep || echo "  no rpc process"
(ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null) | grep 50052 || echo "  port 50052 not listening"
REMOTE
done
