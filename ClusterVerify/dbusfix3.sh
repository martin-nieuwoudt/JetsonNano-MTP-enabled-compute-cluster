#!/bin/bash
KEY=/root/.ssh/id_ed25519
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes"
NODE=jetson@192.168.50.151
SD=/usr/share/dbus-1/system.d

echo "=== push pristine policy files ==="
scp $OPTS /mnt/c/ClusterVerify/dbusd_PolicyKit1.conf  $NODE:/tmp/pk.conf
scp $OPTS /mnt/c/ClusterVerify/dbusd_UbuntuAdvantage.conf $NODE:/tmp/ua.conf
scp $OPTS /mnt/c/ClusterVerify/dbusd_bolt.conf $NODE:/tmp/bolt.conf
scp $OPTS /mnt/c/ClusterVerify/dbusd_fwupd.conf $NODE:/tmp/fwupd.conf
scp $OPTS /mnt/c/ClusterVerify/dbusd_netplan.conf $NODE:/tmp/netplan.conf

ssh $OPTS $NODE '
set -e
SD=/usr/share/dbus-1/system.d
echo "=== remove corrupted bolt.conf (Structure needs cleaning) ==="
sudo rm -f "$SD/org.freedesktop.bolt.conf" 2>&1 || echo "rm bolt failed (will try anyway)"
echo "=== install all policy files ==="
sudo install -m 644 /tmp/pk.conf    "$SD/org.freedesktop.PolicyKit1.conf"
sudo install -m 644 /tmp/ua.conf     "$SD/com.canonical.UbuntuAdvantage.conf"
sudo install -m 644 /tmp/bolt.conf   "$SD/org.freedesktop.bolt.conf"
sudo install -m 644 /tmp/fwupd.conf  "$SD/org.freedesktop.fwupd.conf"
sudo install -m 644 /tmp/netplan.conf "$SD/io.netplan.Netplan.conf"
echo "=== verify all are XML now ==="
for f in "$SD"/*.conf; do
  m=$(sudo head -c 1 "$f")
  if [ "$m" != "<" ]; then echo "STILL CORRUPT: $f"; else echo "OK: $(basename $f)"; fi
done
echo "=== restart dbus-daemon cleanly ==="
sudo pkill -x dbus-daemon 2>/dev/null || true
sleep 1
sudo dbus-daemon --system --fork
sleep 1
pgrep -a dbus-daemon || echo "NO dbus-daemon"
echo "=== start polkit ==="
sudo systemctl start polkit 2>&1 || echo "polkit start issue"
sleep 1
echo "=== start NetworkManager ==="
sudo systemctl start NetworkManager 2>&1 || echo "NM start issue"
sleep 2
pgrep -a NetworkManager || echo "NM NOT running"
echo "=== nmcli test ==="
nmcli -t -f GENERAL.STATE device show eth0 2>&1 | head -2 || echo "nmcli failed"
'
