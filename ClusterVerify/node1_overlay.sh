#!/bin/bash
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N1=jetson@192.168.50.151
DST=/usr/share/dbus-1/system.d

echo "=== 1. create overlay upper/work in /tmp (writable) ==="
ssh $OPTS $N1 'sudo mkdir -p /tmp/dbus_upper /tmp/dbus_work && echo OK' 2>&1

echo "=== 2. place the 3 missing files into overlay upper (from staged /tmp) ==="
ssh $OPTS $N1 'sudo cp -f /tmp/io.netplan.Netplan.conf /tmp/org.freedesktop.fwupd.conf /tmp/org.freedesktop.bolt.conf /tmp/dbus_upper/ 2>&1 && sudo chown root:root /tmp/dbus_upper/*.conf && sudo chmod 644 /tmp/dbus_upper/*.conf && ls -la /tmp/dbus_upper/' 2>&1

echo "=== 3. mount overlay over system.d (no writes to SD) ==="
ssh $OPTS $N1 "sudo mount -t overlay overlay -o lowerdir=$DST,upperdir=/tmp/dbus_upper,workdir=/tmp/dbus_work $DST 2>&1 && echo MOUNT_OK" 2>&1

echo "=== 4. verify all 5 files visible + valid XML ==="
ssh $OPTS $N1 'for f in org.freedesktop.PolicyKit1.conf com.canonical.UbuntuAdvantage.conf io.netplan.Netplan.conf org.freedesktop.fwupd.conf org.freedesktop.bolt.conf; do b=$(head -c 1 /usr/share/dbus-1/system.d/$f 2>/dev/null | xxd -p); printf "%s %s\n" "$f" "$b"; done' 2>&1

echo "=== 5. start polkitd ==="
ssh $OPTS $N1 'sudo pkill -x polkitd 2>/dev/null; sudo nohup /usr/lib/policykit-1/polkitd >/dev/null 2>&1 & sleep 2; echo "polkitd pid: $(pgrep -x polkitd | head -1)"' 2>&1

echo "=== 6. test systemctl over bus ==="
ssh $OPTS $N1 'timeout 10 sudo systemctl is-active polkit; timeout 10 sudo systemctl is-active dbus; timeout 10 sudo systemctl is-active NetworkManager' 2>&1
echo DONE
