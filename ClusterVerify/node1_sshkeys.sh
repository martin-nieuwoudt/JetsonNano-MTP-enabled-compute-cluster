#!/bin/bash
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N1=jetson@192.168.50.151
echo "=== full /etc/ssh listing ==="
ssh $OPTS $N1 'ls -la /etc/ssh/' 2>&1
echo "=== is sshd running? ==="
ssh $OPTS $N1 'pgrep -a sshd || echo "no sshd"; systemctl is-active ssh 2>&1' 2>&1
echo "=== does ssh.service regenerate keys on boot? ==="
ssh $OPTS $N1 'grep -rl "ssh-keygen -A" /etc/systemd/system/ssh.service /lib/systemd/system/ssh.service 2>/dev/null; systemctl cat ssh 2>/dev/null | grep -i "execstart\|keygen" | head' 2>&1
echo DONE
