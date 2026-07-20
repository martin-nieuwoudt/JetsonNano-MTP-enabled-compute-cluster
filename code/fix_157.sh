#!/usr/bin/env bash
# Hard-restart .157 RPC worker and confirm clean UMA + a fresh cudaMalloc test
ssh -o BatchMode=yes jetson@192.168.50.157 'bash -s' <<'EOF'
set -e
sudo systemctl stop llama-rpc.service
sleep 2
# kill any stray
pkill -9 -f ggml-rpc-server 2>/dev/null || true
sleep 1
sudo systemctl start llama-rpc.service
sleep 3
echo "=== proc ==="
pgrep -af ggml-rpc-server | head -1
echo "=== fresh UMA ==="
sudo journalctl -u llama-rpc.service -n 5 --no-pager | grep -i uma || echo "no uma line yet"
EOF
