#!/bin/bash
ssh -i /root/.ssh/id_ed25519 \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ConnectTimeout=10 -o BatchMode=yes \
  jetson@192.168.50.151 \
  'echo "=== /run/dbus contents ==="; ls -l /run/dbus/ 2>&1
echo "=== dbus-daemon procs ==="; pgrep -a dbus-daemon 2>&1 || echo "NO dbus-daemon running"
echo "=== dbus.socket enabled? (sockets.target.wants) ==="; ls -l /etc/systemd/system/sockets.target.wants/dbus.socket 2>&1 || echo "NO dbus.socket symlink"
echo "=== dbus unit files exist? ==="; ls -l /lib/systemd/system/dbus.socket /lib/systemd/system/dbus.service 2>&1
echo "=== /run mount type ==="; mount | grep " on /run " 2>&1 || echo "no /run mount line"
echo "=== system bus socket file? ==="; ls -l /run/dbus/system_bus_socket 2>&1 || echo "SOCKET MISSING"
echo "=== can we open the socket? ==="; (timeout 2 bash -c "echo > /dev/unix/stream//run/dbus/system_bus_socket" 2>&1 && echo "SOCKET OPENABLE" || echo "SOCKET NOT OPENABLE")'
