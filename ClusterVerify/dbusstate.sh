#!/bin/bash
KEY=/root/.ssh/id_ed25519
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes"
NODE=jetson@192.168.50.151

ssh $OPTS $NODE '
echo "=== dbus-daemon ==="; pgrep -a dbus-daemon || echo "NO dbus"
echo "=== polkit ==="; sudo systemctl is-active polkit 2>&1 || true
echo "=== NetworkManager ==="; pgrep -a NetworkManager || echo "NO NM"
echo "=== system.d XML check ==="
for f in /usr/share/dbus-1/system.d/*.conf; do
  m=$(sudo head -c 1 "$f" 2>/dev/null); [ "$m" = "<" ] && echo "OK $(basename $f)" || echo "BAD $(basename $f)"
done
echo "=== nmcli quick ==="; timeout 5 nmcli -t -f GENERAL.STATE device show eth0 2>&1 | head -1 || echo "nmcli timeout"
'
