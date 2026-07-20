#!/bin/bash
KEY=/root/.ssh/id_ed25519
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N1=jetson@192.168.50.151

ssh $OPTS $N1 'bash -s' <<'EOF' 2>&1
echo "=== node1 top-level dbus magic ==="
for f in system.conf session.conf; do
  printf "%s : " "$f"; head -c 4 /usr/share/dbus-1/$f | xxd | head -1
done
echo "=== node1 system.d policy files (first byte should be 3c='<') ==="
for f in /usr/share/dbus-1/system.d/*.conf; do
  b=$(head -c 1 "$f" | xxd -p)
  printf "%s  firstbyte=%s\n" "$(basename "$f")" "$b"
done
echo "=== the 5 previously-bad files specifically ==="
for f in org.freedesktop.PolicyKit1.conf com.canonical.UbuntuAdvantage.conf org.freedesktop.bolt.conf io.netplan.Netplan.conf org.freedesktop.fwupd.conf; do
  if [ -f /usr/share/dbus-1/system.d/$f ]; then
    b=$(head -c 1 /usr/share/dbus-1/system.d/$f | xxd -p)
    printf "%s  firstbyte=%s\n" "$f" "$b"
  else
    echo "$f  MISSING"
  fi
done
echo "=== ext4 'Structure needs cleaning' in dmesg? ==="
dmesg 2>/dev/null | grep -i "structure needs cleaning" | tail -5 || echo "no dmesg access"
echo "=== root mount ==="
mount | grep ' / ' | head -1
echo "=== dbus / polkit / NM status ==="
pgrep -a dbus-daemon | head -2
systemctl is-active dbus 2>&1 || true
systemctl is-active polkit 2>&1 || true
systemctl is-active NetworkManager 2>&1 || true
EOF
