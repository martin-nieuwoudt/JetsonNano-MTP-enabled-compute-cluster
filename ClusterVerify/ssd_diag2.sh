#!/usr/bin/env bash
set -e
ssh -i /home/marti/.ssh/id_ed25519 -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o BatchMode=yes -o ConnectTimeout=10 jetson@192.168.50.150 '
echo "=== df -T -B1 /mnt/ssd ==="
df -T -B1 /mnt/ssd 2>/dev/null
echo "=== df -h /mnt/ssd ==="
df -h /mnt/ssd 2>/dev/null
echo "=== /proc/mounts ssd ==="
grep ssd /proc/mounts
echo "=== smb.conf [ssd] ==="
grep -A6 "\[ssd\]" /etc/samba/smb.conf
echo "=== ls /mnt/ssd ==="
ls -la /mnt/ssd | head
echo "=== mount | grep sda ==="
mount | grep sda
echo "=== lsblk ==="
lsblk
' 2>&1
