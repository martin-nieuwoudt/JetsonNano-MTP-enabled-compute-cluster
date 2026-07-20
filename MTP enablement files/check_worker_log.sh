#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'bash -s' <<'EOF'
echo "=== MTP worker log (tail) ==="
tail -n 25 /home/jetson/mtp_rpc.log
echo "=== still listening? ==="
(ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null) | grep 50053 || echo "NOT LISTENING"
EOF
