#!/bin/bash
ssh -i /root/.ssh/id_ed25519 \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ConnectTimeout=10 -o BatchMode=yes \
  jetson@192.168.50.151 \
  'echo "=== system.conf (head) ==="; sudo head -c 400 /usr/share/dbus-1/system.conf | xxd | head -20
echo "=== file size ==="; sudo wc -c /usr/share/dbus-1/system.conf
echo "=== session.conf ==="; sudo wc -c /usr/share/dbus-1/session.conf 2>&1
echo "=== is system.conf a symlink? ==="; ls -l /usr/share/dbus-1/system.conf
echo "=== dpkg status of dbus ==="; dpkg -l dbus 2>/dev/null | tail -2
echo "=== /etc/dbus-1/system.conf ==="; sudo wc -c /etc/dbus-1/system.conf 2>&1
echo "=== apt cache deb available? ==="; ls -l /var/cache/apt/archives/dbus*_*.deb 2>&1 || echo "no cached deb"'
