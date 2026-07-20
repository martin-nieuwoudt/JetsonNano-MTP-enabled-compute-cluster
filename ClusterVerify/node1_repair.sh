#!/bin/bash
KEY=/root/.ssh/id_ed25519
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N0=jetson@192.168.50.150
N1=jetson@192.168.50.151
DST=/usr/share/dbus-1/system.d
FILES="org.freedesktop.PolicyKit1.conf com.canonical.UbuntuAdvantage.conf io.netplan.Netplan.conf org.freedesktop.fwupd.conf org.freedesktop.bolt.conf"

echo "########## STEP 1: copy 5 pristine files node0 -> node1 (live) ##########"
for f in $FILES; do
  echo "=== $f ==="
  ssh $OPTS $N0 "sudo cat $DST/$f" 2>/dev/null | ssh $OPTS $N1 "sudo rm -f $DST/$f; sudo tee $DST/$f >/dev/null; sudo chmod 644 $DST/$f; sudo chown root:root $DST/$f" 2>&1
  echo "rc=$?"
done

echo "########## STEP 2: restart dbus (systemd socket respawns it) ##########"
ssh $OPTS $N1 'sudo pkill -x dbus-daemon; sleep 2; echo "dbus now: $(pgrep -a dbus-daemon | head -1)"' 2>&1

echo "########## STEP 3: start polkit + NetworkManager ##########"
ssh $OPTS $N1 'sudo systemctl start polkit 2>&1; sudo systemctl restart NetworkManager 2>&1; sleep 3; echo "polkit=$(systemctl is-active polkit 2>&1)"; echo "NM=$(systemctl is-active NetworkManager 2>&1)"; echo "dbus=$(systemctl is-active dbus 2>&1)"' 2>&1

echo "########## STEP 4: verify all system.d files valid XML ##########"
ssh $OPTS $N1 'bad=0; for f in /usr/share/dbus-1/system.d/*.conf; do b=$(head -c 1 "$f" | xxd -p); [ "$b" != "3c" ] && { echo "BAD: $(basename "$f") ($b)"; bad=$((bad+1)); }; done; [ "$bad" -eq 0 ] && echo "ALL system.d FILES VALID XML"' 2>&1

echo "########## STEP 5: systemctl + nmcli functional? ##########"
ssh $OPTS $N1 'echo "--- systemctl list-units (head) ---"; systemctl list-units --type=service 2>&1 | head -5; echo "--- nmcli ---"; nmcli -t -f DEVICE,STATE dev 2>&1 | head -3' 2>&1
echo DONE
