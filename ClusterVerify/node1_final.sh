#!/bin/bash
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N1=jetson@192.168.50.151
echo "=== hostname ==="; ssh $OPTS $N1 'hostname'
echo "=== IP ==="; ssh $OPTS $N1 'ip -br addr show eth0'
echo "=== static method ==="; ssh $OPTS $N1 'nmcli -t -f ipv4.method,ipv4.addresses con show "Wired connection 1"'
echo "=== machine-id ==="; ssh $OPTS $N1 'cat /etc/machine-id'
echo "=== rpc-server ==="; ssh $OPTS $N1 'pgrep -a rpc-server | head -1 || echo "rpc NOT running"'
echo "=== sshd ==="; ssh $OPTS $N1 'systemctl is-active ssh'
echo DONE
