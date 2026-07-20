#!/bin/bash
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N1=jetson@192.168.50.151

echo "=== 1. strip GUI -> headless multi-user.target ==="
ssh $OPTS $N1 'sudo systemctl set-default multi-user.target 2>&1; echo "default now: $(systemctl get-default)"' 2>&1

echo "=== 2. clear SSH host-key fingerprint (regenerate unique on boot) ==="
ssh $OPTS $N1 'sudo rm -f /etc/ssh/ssh_host_*; echo "remaining host keys:"; ls /etc/ssh/ | grep ssh_host || echo "  ALL WIPED"' 2>&1

echo "=== 3. reboot to apply (GUI gone, keys regenerated) ==="
ssh $OPTS $N1 'sudo reboot' 2>&1
echo "reboot issued"
echo DONE
