#!/bin/bash
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N1=jetson@192.168.50.151
echo "=== hostname ==="
ssh $OPTS $N1 'hostname' 2>&1
echo "=== IP + method ==="
ssh $OPTS $N1 'ip -br addr show eth0; echo "---"; nmcli -t -f ipv4.method,ipv4.addresses,ipv4.gateway,ipv4.dns con show "Wired connection 1"' 2>&1
echo "=== machine-id (should be unique, not 33-byte node0 clone) ==="
ssh $OPTS $N1 'wc -c < /etc/machine-id; cat /etc/machine-id' 2>&1
echo "=== ssh host keys regenerated? ==="
ssh $OPTS $N1 'ls /etc/ssh/ | grep host_key || echo "STILL NONE"' 2>&1
echo DONE
