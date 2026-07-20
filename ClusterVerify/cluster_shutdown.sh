#!/bin/bash
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
echo "=== power off node1 (force: dbus degraded, avoid bus hang) ==="
ssh $OPTS jetson@192.168.50.151 'sudo poweroff -f' 2>&1
echo "node1 command sent"
echo "=== power off node0 (clean) ==="
ssh $OPTS jetson@192.168.50.150 'sudo poweroff' 2>&1
echo "node0 command sent"
echo DONE
