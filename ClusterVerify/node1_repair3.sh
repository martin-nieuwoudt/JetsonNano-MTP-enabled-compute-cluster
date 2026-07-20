#!/bin/bash
KEY=/root/.ssh/id_ed25519
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N0=jetson@192.168.50.150
N1=jetson@192.168.50.151
DST=/usr/share/dbus-1/system.d
FILES="org.freedesktop.PolicyKit1.conf com.canonical.UbuntuAdvantage.conf io.netplan.Netplan.conf org.freedesktop.fwupd.conf org.freedesktop.bolt.conf"

echo "=== pull 5 files node0 -> WSL /tmp ==="
for f in $FILES; do
  if ssh $OPTS $N0 "sudo cat $DST/$f" > /tmp/$f 2>/dev/null; then
    echo "pulled $f ($(wc -c < /tmp/$f) bytes)"
  else
    echo "PULL FAILED $f"
  fi
done

echo "=== push WSL /tmp -> node1 /tmp ==="
for f in $FILES; do
  if scp $OPTS /tmp/$f $N1:/tmp/$f 2>/dev/null; then
    echo "pushed $f"
  else
    echo "PUSH FAILED $f"
  fi
done

echo "=== install on node1 (sudo mv) ==="
for f in $FILES; do
  ssh $OPTS $N1 "sudo mv -f /tmp/$f $DST/$f && sudo chown root:root $DST/$f && sudo chmod 644 $DST/$f" 2>&1 && echo "installed $f"
done

echo "=== verify magic bytes on node1 ==="
ssh $OPTS $N1 'for f in org.freedesktop.PolicyKit1.conf com.canonical.UbuntuAdvantage.conf io.netplan.Netplan.conf org.freedesktop.fwupd.conf org.freedesktop.bolt.conf; do b=$(head -c 1 /usr/share/dbus-1/system.d/$f 2>/dev/null | xxd -p); printf "%s %s\n" "$f" "$b"; done' 2>&1

echo "=== start polkitd directly ==="
ssh $OPTS $N1 'sudo pkill -x polkitd 2>/dev/null; sudo nohup /usr/lib/policykit-1/polkitd >/dev/null 2>&1 & sleep 2; echo "polkitd pid: $(pgrep -x polkitd | head -1)"' 2>&1

echo "=== test systemctl over bus ==="
ssh $OPTS $N1 'timeout 10 sudo systemctl is-active polkit; timeout 10 sudo systemctl is-active dbus; timeout 10 sudo systemctl is-active NetworkManager' 2>&1
echo DONE
