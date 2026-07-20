#!/bin/bash
IMG=/mnt/c/ClusterVerify/Jetson_NanoZero_Baseline.img
OFFSET=$((28672 * 512))
FILESZ=$(stat -c %s "$IMG")
SIZELIMIT=$((FILESZ - OFFSET))
LOOP=$(losetup -f --show -o "$OFFSET" --sizelimit "$SIZELIMIT" "$IMG")
echo "LOOP=$LOOP"
echo "=== dumpe2fs superblock (head) ==="
dumpe2fs -h "$LOOP" 2>&1 | head -30 || true
echo "=== fsck.ext4 -n (non-destructive) ==="
fsck.ext4 -n "$LOOP" 2>&1 | head -50 || true
losetup -d "$LOOP" 2>/dev/null || true
echo DONE
