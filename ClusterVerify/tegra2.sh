#!/bin/bash
KEY=/root/.ssh/id_ed25519
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
NODE=jetson@192.168.50.151

ssh $OPTS $NODE 'bash -s' <<'EOF' 2>&1
echo "=== whoami / groups ==="
whoami; id
echo "=== tegrastats binary ==="
ls -l /usr/bin/tegrastats 2>&1 || echo "MISSING"
echo "=== try tegrastats as jetson (2s) ==="
timeout 4 tegrastats --interval 1000 2>&1 | head -1 || echo "rc=$?"
echo "=== try sudo tegrastats (2s) ==="
timeout 4 sudo tegrastats --interval 1000 2>&1 | head -1 || echo "rc=$?"
echo "=== thermal zones ==="
for f in /sys/devices/virtual/thermal/thermal_zone*/temp; do printf "%s = " "$f"; cat "$f" 2>/dev/null; echo; done | head -8
EOF
