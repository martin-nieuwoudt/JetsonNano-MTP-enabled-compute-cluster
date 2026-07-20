#!/bin/bash
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N1=jetson@192.168.50.151
echo "=== default target ==="
ssh $OPTS $N1 'systemctl get-default' 2>&1
echo "=== ssh host keys ==="
ssh $OPTS $N1 'ls /etc/ssh/ | grep ssh_host || echo "ALL WIPED"' 2>&1
echo "=== uptime (to see if reboot happened) ==="
ssh $OPTS $N1 'uptime' 2>&1
echo DONE
