#!/bin/bash
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N1=jetson@192.168.50.151
echo "=== hostname ==="
ssh $OPTS $N1 'hostname' 2>&1
echo "=== IP addrs ==="
ssh $OPTS $N1 'ip -br addr show eth0' 2>&1
echo "=== default target ==="
ssh $OPTS $N1 'systemctl get-default' 2>&1
echo "=== ssh host keys present? ==="
ssh $OPTS $N1 'ls /etc/ssh/ | grep host_key || echo "NONE (will regenerate)"' 2>&1
echo "=== machine-id size ==="
ssh $OPTS $N1 'wc -c < /etc/machine-id' 2>&1
echo "=== dbus system.d count + any non-XML ==="
ssh $OPTS $N1 'd=$(ls /usr/share/dbus-1/system.d/*.conf); n=0; bad=0; for f in $d; do b=$(head -c1 "$f" | xxd -p); [ "$b" != "3c" ] && { bad=$((bad+1)); echo "BAD $f ($b)"; }; n=$((n+1)); done; echo "total=$n bad=$bad"' 2>&1
echo "=== rpc-server running? ==="
ssh $OPTS $N1 'pgrep -a rpc-server | head -1 || echo "rpc NOT running"' 2>&1
echo DONE
