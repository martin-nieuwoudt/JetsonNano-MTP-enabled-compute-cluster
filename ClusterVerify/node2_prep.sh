#!/bin/bash
# node2_prep.sh — onboard the second Jetson Nano worker (192.168.50.152 / nano02).
# Mirrors node1_prep.sh but targets node2. Idempotent where safe.
KEY=/home/marti/.ssh/id_ed25519_vm
OPTS="-i $KEY -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N2=jetson@192.168.50.152

echo "=== 1. wipe machine-id (regenerate unique) ==="
ssh $OPTS $N2 'sudo rm -f /etc/machine-id; sudo systemd-machine-id-setup 2>&1; echo "new machine-id: $(cat /etc/machine-id)"' 2>&1

echo "=== 2. set unique hostname nano02 ==="
ssh $OPTS $N2 'sudo hostnamectl set-hostname nano02 2>&1; echo "hostname now: $(hostname)"' 2>&1

echo "=== 3. ensure static IP .152 (idempotent) ==="
ssh $OPTS $N2 'sudo nmcli con mod "Wired connection 1" ipv4.method manual ipv4.addresses 192.168.50.152/24 ipv4.gateway 192.168.50.1 ipv4.dns 192.168.50.1 2>&1; sudo nmcli con up "Wired connection 1" 2>&1; ip -br addr show eth0' 2>&1

echo "=== 4. verify ssh host keys regenerated ==="
ssh $OPTS $N2 'ls /etc/ssh/ | grep host_key || echo "STILL NONE"' 2>&1

echo "=== 5. reboot to apply machine-id/hostname cleanly ==="
ssh $OPTS $N2 'sudo reboot' 2>&1
echo "reboot issued"
echo DONE
