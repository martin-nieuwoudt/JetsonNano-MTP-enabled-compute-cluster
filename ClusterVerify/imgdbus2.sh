#!/bin/bash
IMG=/mnt/c/ClusterVerify/Jetson_NanoZero_Baseline.img
OFFSET=$((28672 * 512))
FILESZ=$(stat -c %s "$IMG")
SIZELIMIT=$((FILESZ - OFFSET))
LOOP=$(losetup -f --show -o "$OFFSET" --sizelimit "$SIZELIMIT" "$IMG")
echo "LOOP=$LOOP"
echo "=== root dir ==="
debugfs -R "ls -l /" "$LOOP" 2>&1 | head -30
echo "=== /usr dir ==="
debugfs -R "ls -l /usr" "$LOOP" 2>&1 | head -20
echo "=== /usr/share dir ==="
debugfs -R "ls -l /usr/share" "$LOOP" 2>&1 | head -20
echo "=== try stat system.conf ==="
debugfs -R "stat /usr/share/dbus-1/system.conf" "$LOOP" 2>&1 | head -20
losetup -d "$LOOP" 2>/dev/null || true
echo DONE
