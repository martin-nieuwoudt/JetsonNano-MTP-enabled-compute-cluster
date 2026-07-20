#!/bin/bash
IMG=/mnt/c/ClusterVerify/Jetson_NanoZero_Baseline.img
MNT=/mnt/imgroot
OFFSET=$((28672 * 512))          # APP partition start sector
FILESZ=$(stat -c %s "$IMG")
SIZELIMIT=$((FILESZ - OFFSET))
echo "OFFSET=$OFFSET  SIZELIMIT=$SIZELIMIT  ($((SIZELIMIT/1024/1024)) MiB available of 58GiB partition)"

LOOP=$(losetup -f --show -o "$OFFSET" --sizelimit "$SIZELIMIT" "$IMG")
echo "LOOP=$LOOP"
mkdir -p "$MNT"
if mount -o ro "$LOOP" "$MNT" 2>&1; then
  echo "MOUNTED OK"
  echo "=== dbus top-level magic (first 4 bytes; 3c21='<!--' = valid XML) ==="
  for f in system.conf session.conf; do
    printf "%s : " "$f"; head -c 4 "$MNT/usr/share/dbus-1/$f" 2>/dev/null | xxd | head -1 || echo "MISSING"
  done
  echo "=== system.d policy files (first byte should be 3c='<') ==="
  for f in "$MNT"/usr/share/dbus-1/system.d/*.conf; do
    b=$(head -c 1 "$f" 2>/dev/null | xxd -p)
    printf "%s  firstbyte=%s\n" "$(basename "$f")" "$b"
  done
  echo "=== fsck.ext4 -n (non-destructive) ==="
  fsck.ext4 -n "$LOOP" 2>&1 | head -40
  umount "$MNT" 2>/dev/null || true
else
  echo "MOUNT FAILED"
fi
losetup -d "$LOOP" 2>/dev/null || true
echo DONE
