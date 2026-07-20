#!/bin/bash
IMG=/mnt/c/ClusterVerify/Jetson_NanoZero_Baseline.img
OFFSET=$((28672 * 512))
FILESZ=$(stat -c %s "$IMG")
SIZELIMIT=$((FILESZ - OFFSET))
LOOP=$(losetup -f --show -o "$OFFSET" --sizelimit "$SIZELIMIT" "$IMG")
echo "LOOP=$LOOP"
echo "=== catastrophic mode: stat dbus dir + system.conf ==="
debugfs -c -R "stat /usr/share/dbus-1/system.conf" "$LOOP" 2>&1 | head -25
echo "=== cat system.conf (catastrophic) ==="
debugfs -c -R "cat /usr/share/dbus-1/system.conf" "$LOOP" 2>&1 | head -c 300
echo
echo "=== ls system.d (catastrophic) ==="
debugfs -c -R "ls -l /usr/share/dbus-1/system.d" "$LOOP" 2>&1 | head -40
losetup -d "$LOOP" 2>/dev/null || true
echo DONE
