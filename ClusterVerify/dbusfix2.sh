#!/bin/bash
set -e
KEY=/root/.ssh/id_ed25519
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes"
NODE=jetson@192.168.50.151

echo "=== STEP 1: push pristine configs ==="
scp $OPTS /mnt/c/ClusterVerify/dbus_system.conf  $NODE:/tmp/system.conf
scp $OPTS /mnt/c/ClusterVerify/dbus_session.conf $NODE:/tmp/session.conf

ssh $OPTS $NODE '
set -e
echo "=== STEP 2: install configs (backup the corrupted ELF first) ==="
sudo cp /usr/share/dbus-1/system.conf  /usr/share/dbus-1/system.conf.corrupt.bak 2>/dev/null || true
sudo cp /usr/share/dbus-1/session.conf /usr/share/dbus-1/session.conf.corrupt.bak 2>/dev/null || true
sudo install -m 644 /tmp/system.conf  /usr/share/dbus-1/system.conf
sudo install -m 644 /tmp/session.conf /usr/share/dbus-1/session.conf
echo "system.conf magic now:"; sudo head -c 4 /usr/share/dbus-1/system.conf | xxd
echo "session.conf magic now:"; sudo head -c 4 /usr/share/dbus-1/session.conf | xxd

echo "=== STEP 3: ensure dbus.socket enabled for boot ==="
sudo mkdir -p /etc/systemd/system/sockets.target.wants
if [ ! -e /etc/systemd/system/sockets.target.wants/dbus.socket ]; then
  sudo ln -sf /lib/systemd/system/dbus.socket /etc/systemd/system/sockets.target.wants/dbus.socket
  echo "dbus.socket symlink created"
fi

echo "=== STEP 4: start dbus-daemon (system bus) ==="
if ! pgrep -x dbus-daemon >/dev/null; then
  sudo dbus-daemon --system --fork
  echo "dbus-daemon launched"
fi
sleep 1

echo "=== STEP 5: verify ==="
pgrep -a dbus-daemon || echo "STILL NO dbus-daemon"
ls -l /run/dbus/system_bus_socket
echo "--- test systemctl over bus ---"
sudo systemctl is-active dbus.service 2>&1 || true
echo "--- test nmcli over bus ---"
nmcli -t -f GENERAL.STATE device show eth0 2>&1 | head -2 || echo "nmcli still failing"
'
