#!/usr/bin/env bash
# Stop the legacy port-50053 MTP test instances so the proven binary can be
# overwritten and the systemd-managed 50052 daemon can take over fleet-wide.
for n in 151 152 153; do
  ip="192.168.50.$n"
  echo "=== $ip : killing 50053 test instance ==="
  ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no jetson@$ip \
    'pkill -f "ggml-rpc-server.*50053" && echo "  killed" || echo "  none running"'
done
echo "DONE"
