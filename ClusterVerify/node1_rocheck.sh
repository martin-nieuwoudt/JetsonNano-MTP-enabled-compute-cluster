#!/bin/bash
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N1=jetson@192.168.50.151
echo "=== node1 dbus system.d status (read-only) ==="
ssh $OPTS $N1 'for f in org.freedesktop.PolicyKit1.conf com.canonical.UbuntuAdvantage.conf io.netplan.Netplan.conf org.freedesktop.fwupd.conf org.freedesktop.bolt.conf; do
  if [ -f /usr/share/dbus-1/system.d/$f ]; then b=$(head -c 1 /usr/share/dbus-1/system.d/$f | xxd -p); echo "$f PRESENT firstbyte=$b";
  else echo "$f MISSING"; fi
done' 2>&1
echo "=== leftover staged files in /tmp on node1 ==="
ssh $OPTS $N1 'ls -la /tmp/*.conf 2>/dev/null' 2>&1
echo "=== RPC still up? ==="
ssh $OPTS $N1 'pgrep -a rpc-server | head -1' 2>&1
echo DONE
