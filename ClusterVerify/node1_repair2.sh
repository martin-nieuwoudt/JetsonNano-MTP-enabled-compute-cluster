#!/bin/bash
KEY=/root/.ssh/id_ed25519
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N0=jetson@192.168.50.150
N1=jetson@192.168.50.151
FILES="org.freedesktop.PolicyKit1.conf com.canonical.UbuntuAdvantage.conf io.netplan.Netplan.conf org.freedesktop.fwupd.conf org.freedesktop.bolt.conf"

echo "=== copy 5 pristine files node0 -> node1 (NO NM restart) ==="
for f in $FILES; do
  if ssh $OPTS $N0 "sudo cat /usr/share/dbus-1/system.d/$f" | ssh $OPTS $N1 "sudo tee /usr/share/dbus-1/system.d/$f >/dev/null" 2>/dev/null; then
    echo "copied $f"
  else
    echo "FAILED $f"
  fi
done

echo "=== verify magic bytes on node1 ==="
ssh $OPTS $N1 'for f in org.freedesktop.PolicyKit1.conf com.canonical.UbuntuAdvantage.conf io.netplan.Netplan.conf org.freedesktop.fwupd.conf org.freedesktop.bolt.conf; do b=$(head -c 1 /usr/share/dbus-1/system.d/$f 2>/dev/null | xxd -p); printf "%s %s\n" "$f" "$b"; done' 2>&1

echo "=== start polkitd directly (bypass systemctl to avoid bus-auth hang) ==="
ssh $OPTS $N1 'sudo pkill -x polkitd 2>/dev/null; sudo nohup /usr/lib/policykit-1/polkitd >/dev/null 2>&1 & sleep 2; echo "polkitd pid: $(pgrep -x polkitd | head -1)"' 2>&1

echo "=== test systemctl over bus (quick) ==="
ssh $OPTS $N1 'timeout 10 sudo systemctl is-active polkit; timeout 10 sudo systemctl is-active dbus; timeout 10 sudo systemctl is-active NetworkManager' 2>&1
echo DONE
