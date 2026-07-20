#!/bin/bash
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes"
ssh $OPTS jetson@192.168.50.150 bash -s <<'EOF'
echo "=== /proc/mounts /mnt/ssd ==="
grep ' /mnt/ssd ' /proc/mounts
echo "=== mount | grep sda ==="
mount | grep sda
echo "=== touch probe ==="
cd /mnt/ssd && (touch .telemetry_probe 2>&1 && echo WRITE_OK && rm -f .telemetry_probe || echo WRITE_FAIL)
echo "=== dmesg ro/remount ==="
dmesg 2>/dev/null | grep -iE 'sda|ext4|read-only|remount' | tail -n 15
echo "=== fsck hint (no run) ==="
sudo tune2fs -l /dev/sda1 2>/dev/null | grep -iE 'state|mount count|check'
EOF
echo DONE
