#!/bin/bash
KEY=/root/.ssh/id_ed25519
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
NODE=jetson@192.168.50.150

ssh $OPTS $NODE 'bash -s' <<'EOF' 2>&1
echo "=== node0 top-level dbus magic ==="
for f in system.conf session.conf; do
  printf "%s : " "$f"; head -c 4 /usr/share/dbus-1/$f | xxd | head -1
done
echo "=== node0 system.d policy files (first byte should be 3c='<') ==="
for f in /usr/share/dbus-1/system.d/*.conf; do
  b=$(head -c 1 "$f" | xxd -p)
  printf "%s  firstbyte=%s\n" "$(basename "$f")" "$b"
done
echo "=== count non-XML (first byte != 3c) ==="
bad=0
for f in /usr/share/dbus-1/system.d/*.conf; do
  b=$(head -c 1 "$f" | xxd -p)
  [ "$b" != "3c" ] && { echo "BAD: $(basename "$f") ($b)"; bad=$((bad+1)); }
done
[ "$bad" -eq 0 ] && echo "ALL system.d FILES VALID XML"
echo "=== ext4 'Structure needs cleaning' check ==="
dmesg 2>/dev/null | grep -i "structure needs cleaning" | head -3 || echo "no dmesg access / none"
echo "=== fsck not runnable on live mount; check for read-only remount ==="
mount | grep ' / ' | head -1
EOF
