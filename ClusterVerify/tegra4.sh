#!/bin/bash
KEY=/root/.ssh/id_ed25519
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
NODE=jetson@192.168.50.151

ssh $OPTS $NODE 'bash -s' <<'EOF' 2>&1
echo "=== tegrastats -d 1 (self-exits) ==="
tegrastats --interval 1000 -d 1 2>/dev/null | head -1
echo "rc=$?"
EOF
