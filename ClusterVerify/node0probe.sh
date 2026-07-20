#!/bin/bash
KEY=/root/.ssh/id_ed25519
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes"
NODE=jetson@192.168.50.150

echo "=== reachability ==="
ping -c 2 -W 2 192.168.50.150 2>&1 | tail -3 || echo "ping failed"
echo "=== sshd listening? ==="
ssh $OPTS $NODE 'echo "SSH OK";
echo "--- sshd procs ---"; pgrep -a sshd || echo "NO sshd"
echo "--- rpc-server? ---"; pgrep -a rpc-server || echo "NO rpc-server (expected on template)"
echo "--- GUI/display? ---"; pgrep -f "Xorg|gdm|lightdm" || echo "no display server"
echo "--- RAM avail ---"; awk "/MemAvailable/ {print \$2}" /proc/meminfo
echo "--- default target ---"; systemctl get-default 2>&1
echo "--- dbus bus present? ---"; ls -l /run/dbus/system_bus_socket 2>&1
echo "--- dbus-daemon? ---"; pgrep -a dbus-daemon || echo "NO dbus-daemon"
echo "--- system.conf magic ---"; head -c 4 /usr/share/dbus-1/system.conf | xxd
' 2>&1
