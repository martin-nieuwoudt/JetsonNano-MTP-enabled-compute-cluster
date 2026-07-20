#!/usr/bin/env bash
ssh -o BatchMode=yes jetson@192.168.50.154 bash -s <<'EOF'
set -e
echo "=== restart llama-rpc.service ==="
sudo systemctl restart llama-rpc.service
sleep 3
echo "=== status ==="
systemctl is-active llama-rpc.service
echo "=== port ==="
ss -ltnp 2>/dev/null | grep 50052 || echo "not listening"
echo "=== recent log ==="
journalctl -u llama-rpc.service -n 8 --no-pager
EOF
