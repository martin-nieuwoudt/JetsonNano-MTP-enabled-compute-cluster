#!/bin/bash
IMG=/mnt/c/ClusterVerify/Jetson_NanoZero_Baseline.img
OFFSET=$((28672 * 512))
FILESZ=$(stat -c %s "$IMG")
SIZELIMIT=$((FILESZ - OFFSET))
LOOP=$(losetup -f --show -o "$OFFSET" --sizelimit "$SIZELIMIT" "$IMG")
echo "LOOP=$LOOP"
DB=/usr/share/dbus-1
echo "=== top-level dbus configs (first bytes via debugfs cat) ==="
for f in system.conf session.conf; do
  echo "--- $f ---"
  debugfs -R "cat $DB/$f" "$LOOP" 2>/dev/null | head -c 200
  echo
done
echo "=== system.d policy files (first byte should be '<') ==="
# list the directory
debugfs -R "ls -l $DB/system.d" "$LOOP" 2>/dev/null | awk '{print $NF}' | grep '\.conf$' | while read f; do
  b=$(debugfs -R "cat $DB/system.d/$f" "$LOOP" 2>/dev/null | head -c 1 | xxd -p)
  printf "%s  firstbyte=%s\n" "$f" "$b"
done
losetup -d "$LOOP" 2>/dev/null || true
echo DONE
