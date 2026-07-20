#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'bash -s' <<'EOF'
echo "=== listening RPC ports ==="
(ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null) | grep -E '5005[0-9]' || echo "none"
echo "=== systemd llama units (live fleet) ==="
systemctl list-units --type=service --no-pager 2>/dev/null | grep -iE 'llama|rpc' || echo "no systemd units active"
echo "=== my MTP test worker ==="
pgrep -af ggml-rpc-server || echo "no ggml-rpc-server process"
EOF
