#!/bin/bash
set -e
IMG=/mnt/c/ClusterVerify/Jetson_NanoZero_Baseline.img
MNT=/mnt/imgroot

echo "=== partition table ==="
fdisk -l "$IMG" 2>&1 || true

echo "=== set up loop device (partition scan) ==="
LOOP=$(losetup -f --show -P "$IMG")
echo "LOOP=$LOOP"
ls -l ${LOOP}* 2>&1 || true

echo "=== blkid ==="
blkid ${LOOP}* 2>&1 || true

mkdir -p "$MNT"
# Try mounting each partition read-only until one has /usr/share/dbus-1
for p in ${LOOP}p*; do
  echo "--- trying $p ---"
  if mount -o ro "$p" "$MNT" 2>/dev/null; then
    if [ -d "$MNT/usr/share/dbus-1" ]; then
      echo "ROOTFS FOUND on $p"
      echo "=== dbus top-level magic ==="
      for f in system.conf session.conf; do
        printf "%s : " "$f"; head -c 4 "$MNT/usr/share/dbus-1/$f" | xxd | head -1
      done
      echo "=== system.d policy files magic (first byte should be 3c = '<') ==="
      for f in "$MNT"/usr/share/dbus-1/system.d/*.conf; do
        b=$(head -c 1 "$f" | xxd -p)
        printf "%s  firstbyte=%s\n" "$(basename "$f")" "$b"
      done
      umount "$MNT" 2>/dev/null || true
      break
    fi
    umount "$MNT" 2>/dev/null || true
  fi
done
echo "=== cleanup ==="
losetup -d "$LOOP" 2>/dev/null || true
echo DONE
