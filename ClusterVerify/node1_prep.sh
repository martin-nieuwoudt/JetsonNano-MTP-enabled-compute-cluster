#!/bin/bash
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N1=jetson@192.168.50.151

echo "=== 1. wipe machine-id (regenerate unique) ==="
ssh $OPTS $N1 'sudo rm -f /etc/machine-id; sudo systemd-machine-id-setup 2>&1; echo "new machine-id: $(cat /etc/machine-id)"' 2>&1

echo "=== 2. set unique hostname nano01 ==="
ssh $OPTS $N1 'sudo hostnamectl set-hostname nano01 2>&1; echo "hostname now: $(hostname)"' 2>&1

echo "=== 3. ensure static IP .151 (idempotent) ==="
ssh $OPTS $N1 'sudo nmcli con mod "Wired connection 1" ipv4.method manual ipv4.addresses 192.168.50.151/24 ipv4.gateway 192.168.50.1 ipv4.dns 192.168.50.1 2>&1; sudo nmcli con up "Wired connection 1" 2>&1; ip -br addr show eth0' 2>&1

echo "=== 4. verify ssh host keys regenerated ==="
ssh $OPTS $N1 'ls /etc/ssh/ | grep host_key || echo "STILL NONE"' 2>&1

echo "=== 5. reboot to apply machine-id/hostname cleanly ==="
ssh $OPTS $N1 'sudo reboot' 2>&1
echo "reboot issued"
echo DONE
