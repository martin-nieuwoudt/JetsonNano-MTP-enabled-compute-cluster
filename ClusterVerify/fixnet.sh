#!/bin/bash
set -e
for i in $(seq 1 15); do [ -b /dev/sde1 ] && break; sleep 1; done
mkdir -p /mnt/card
mount -o rw /dev/sde1 /mnt/card
CONN="/mnt/card/etc/NetworkManager/system-connections/Wired connection 1.nmconnection"
echo "=== BEFORE ==="
cat "$CONN" 2>&1 || echo "NO CONN FILE"
sed -i -E '
  /^\[ipv4\]/,/^\[/ s/^method=.*/method=auto/;
  /^address[0-9]=/d;
  /^gateway=/d;
  /^dns=/d;
  /^dns-search=/d;
  /^route[0-9]=/d;
  /^mac-address=/d;
  /^interface-name=/d;
  s/^autoconnect=.*/autoconnect=true/;
' "$CONN"
echo "=== AFTER ==="
cat "$CONN" 2>&1
echo "=== SSH SYMLINK ==="
ls -l /mnt/card/etc/systemd/system/multi-user.target.wants/ssh.service 2>&1
umount /mnt/card
echo DONE
