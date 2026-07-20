#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'bash -s' <<'EOF'
echo "=== MTP worker (50053) still listening? ==="
(ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null) | grep 50053 || echo "NOT LISTENING"
echo "=== process ==="
pgrep -af ggml-rpc-server || echo "no process"
EOF
