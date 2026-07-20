#!/bin/bash
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N1=jetson@192.168.50.151
echo "=== bolt.conf content check (overlay) ==="
ssh $OPTS $N1 'head -c 60 /usr/share/dbus-1/system.d/org.freedesktop.bolt.conf; echo' 2>&1
echo "=== start polkitd ==="
ssh $OPTS $N1 'sudo pkill -x polkitd 2>/dev/null; sudo nohup /usr/lib/policykit-1/polkitd >/dev/null 2>&1 & sleep 2; echo "polkitd pid: $(pgrep -x polkitd | head -1)"' 2>&1
echo "=== test systemctl over bus ==="
ssh $OPTS $N1 'timeout 10 sudo systemctl is-active polkit; timeout 10 sudo systemctl is-active dbus; timeout 10 sudo systemctl is-active NetworkManager' 2>&1
echo DONE
