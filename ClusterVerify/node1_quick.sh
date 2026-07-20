#!/bin/bash
KEY=/root/.ssh/id_ed25519
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N1=jetson@192.168.50.151

echo "=== node1: 5 files valid XML? ==="
ssh $OPTS $N1 'bad=0; for f in org.freedesktop.PolicyKit1.conf com.canonical.UbuntuAdvantage.conf io.netplan.Netplan.conf org.freedesktop.fwupd.conf org.freedesktop.bolt.conf; do
  if [ -f /usr/share/dbus-1/system.d/$f ]; then
    b=$(head -c 1 /usr/share/dbus-1/system.d/$f | xxd -p)
    printf "%s firstbyte=%s\n" "$f" "$b"; [ "$b" != "3c" ] && bad=$((bad+1))
  else echo "$f MISSING"; bad=$((bad+1)); fi
done; [ "$bad" -eq 0 ] && echo "ALL 5 RESTORED VALID XML"' 2>&1

echo "=== node1: dbus-daemon + polkit + NM ==="
ssh $OPTS $N1 'pgrep -a dbus-daemon | head -1; echo "polkit pid: $(pgrep -x polkitd | head -1)"; echo "NM pid: $(pgrep -x NetworkManager | head -1)"' 2>&1
echo DONE
