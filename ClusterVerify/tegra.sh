#!/bin/bash
KEY=/root/.ssh/id_ed25519
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes"
NODE=jetson@192.168.50.151

ssh $OPTS $NODE '
echo "=== tegrastats present? ==="
which tegrastats 2>&1 || echo "NO tegrastats in PATH"
ls -l /usr/bin/tegrastats 2>&1 || true
echo "=== run tegrastats (2s) ==="
timeout 3 tegrastats --interval 1000 2>&1 | head -3 || echo "tegrastats failed rc=$?"
echo "=== which thermal zones exist? ==="
ls /sys/devices/virtual/thermal/thermal_zone*/temp 2>&1 | head
echo "=== read thermal zones directly ==="
for f in /sys/devices/virtual/thermal/thermal_zone*/temp; do
  echo "$f = $(cat $f 2>/dev/null) ($(awk "{printf \"%.1fC\", \$1/1000}") )"
done 2>&1 | head -10
echo "=== sensors cmd? ==="
which sensors 2>&1 || echo "no lm-sensors"
' 2>&1
