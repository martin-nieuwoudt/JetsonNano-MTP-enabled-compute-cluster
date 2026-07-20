#!/bin/bash
ssh -i /root/.ssh/id_ed25519 \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ConnectTimeout=10 -o BatchMode=yes \
  jetson@192.168.50.151 \
  'set -e
echo "=== STEP 1: enable dbus.socket (socket activation) ==="
sudo systemctl enable dbus.socket 2>&1 || echo "systemctl enable failed, will symlink manually"
# manual fallback if systemctl could not reach bus
if [ ! -e /etc/systemd/system/sockets.target.wants/dbus.socket ]; then
  sudo mkdir -p /etc/systemd/system/sockets.target.wants
  sudo ln -sf /lib/systemd/system/dbus.socket /etc/systemd/system/sockets.target.wants/dbus.socket
  echo "manual symlink created"
fi
echo "=== STEP 2: start dbus ==="
sudo systemctl start dbus.service 2>&1 || echo "systemctl start failed, launching daemon directly"
# direct fallback
if ! pgrep -x dbus-daemon >/dev/null; then
  sudo dbus-daemon --system --fork
  echo "dbus-daemon launched directly"
fi
sleep 1
echo "=== STEP 3: verify ==="
pgrep -a dbus-daemon 2>&1 || echo "STILL NO dbus-daemon"
ls -l /run/dbus/system_bus_socket 2>&1
echo "=== STEP 4: test systemctl over the bus ==="
sudo systemctl is-active dbus.service 2>&1 || true
sudo systemctl status ssh.service --no-pager 2>&1 | head -3 || true
echo "=== STEP 5: test nmcli over the bus ==="
nmcli -t -f GENERAL.STATE device show eth0 2>&1 | head -2 || echo "nmcli still failing"'
