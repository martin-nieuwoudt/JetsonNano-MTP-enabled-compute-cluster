#!/bin/bash
KEY=/root/.ssh/id_ed25519
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes"
NODE=jetson@192.168.50.151

ssh $OPTS $NODE '
echo "=== try to start NetworkManager over the now-working bus ==="
sudo systemctl start NetworkManager 2>&1 || echo "start failed"
sleep 2
pgrep -a NetworkManager 2>&1 || echo "NM still not running"
echo "=== nmcli test ==="
nmcli -t -f GENERAL.STATE device show eth0 2>&1 | head -2 || echo "nmcli failed"
echo "=== polkit status (was corrupted) ==="
sudo systemctl status polkit 2>&1 | head -3 || true
echo "=== fs corruption check: dmesg ext4 ==="
sudo dmesg 2>/dev/null | grep -i "ext4\|structure needs cleaning\|I/O error" | tail -5 || echo "no dmesg access"
'
