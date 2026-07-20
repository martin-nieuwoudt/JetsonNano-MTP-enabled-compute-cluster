#!/bin/bash
echo "===== NODE0 (.150) dbus configs ====="
ssh -i /root/.ssh/id_ed25519 \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ConnectTimeout=10 -o BatchMode=yes \
  jetson@192.168.50.150 \
  'echo "--- system.conf magic ---"; head -c 4 /usr/share/dbus-1/system.conf | xxd
echo "--- system.conf size ---"; wc -c /usr/share/dbus-1/system.conf
echo "--- session.conf magic ---"; head -c 4 /usr/share/dbus-1/session.conf | xxd
echo "--- session.conf size ---"; wc -c /usr/share/dbus-1/session.conf
echo "--- dbus version ---"; dpkg-query -W -f="\${Version}\n" dbus 2>/dev/null || dbus-daemon --version | head -1' 2>&1
echo ""
echo "===== NODE1 (.151) dbus configs ====="
ssh -i /root/.ssh/id_ed25519 \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ConnectTimeout=10 -o BatchMode=yes \
  jetson@192.168.50.151 \
  'echo "--- system.conf magic ---"; sudo head -c 4 /usr/share/dbus-1/system.conf | xxd
echo "--- session.conf magic ---"; sudo head -c 4 /usr/share/dbus-1/session.conf | xxd
echo "--- dbus version ---"; dpkg-query -W -f="\${Version}\n" dbus 2>/dev/null || dbus-daemon --version | head -1' 2>&1
