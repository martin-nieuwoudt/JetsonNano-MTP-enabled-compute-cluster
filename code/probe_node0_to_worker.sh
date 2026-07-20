#!/bin/bash
# probe_node0_to_worker.sh - test if node0 can SSH to a worker (for direct copy)
ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=no jetson@192.168.50.150 bash -s <<'REMOTE'
echo "node0 uptime: $(uptime)"
for ip in 151 152 153 154 155 156 157 158 159 160; do
  if ssh -o BatchMode=yes -o ConnectTimeout=5 -o StrictHostKeyChecking=no jetson@192.168.50.$ip 'echo "  worker .'$ip' reachable"' 2>/dev/null; then
    :
  else
    echo "  worker .$ip UNREACHABLE from node0"
  fi
done
REMOTE
