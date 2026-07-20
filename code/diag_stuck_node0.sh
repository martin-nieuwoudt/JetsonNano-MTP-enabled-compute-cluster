#!/usr/bin/env bash
# Check why the client is wedged: node0 rpc server log + all-node rpc alive
ssh -i /home/marti/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=no jetson@192.168.50.150 bash -s <<'EOF'
echo "=== NODE0 rpc-server journal (last 20) ==="
journalctl -u ggml-rpc-server --no-pager -n 20 2>/dev/null || \
  (pgrep -af ggml-rpc; echo "--- no journal unit, showing ps ---")
echo
echo "=== NODE0 load ==="
uptime
echo
echo "=== NODE0 mem (is shard loaded?) ==="
free -m | head -2
EOF
echo "=== ALL NODES: rpc proc count ==="
for ip in 150 151 152 153 154 155 156 157 158 159 160; do
  printf "%s:" "$ip"
  wsl none 2>/dev/null
  ssh -i /home/marti/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=4 jetson@192.168.50.$ip "pgrep -c ggml-rpc-server || echo 0" 2>/dev/null || echo SSHFAIL
done
