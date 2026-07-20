#!/bin/bash
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N0=jetson@192.168.50.150
echo "=== /mnt/ssd contents (what the share currently serves) ==="
ssh $OPTS $N0 'ls -la /mnt/ssd 2>&1 | head; echo "--- autofs map ---"; cat /etc/auto.master 2>/dev/null | grep -v "^#" | grep -v "^$"; cat /etc/auto.* 2>/dev/null | grep -v "^#" | grep -v "^$"'
echo "=== is /mnt/ssd the SSD or empty? ==="
ssh $OPTS $N0 'df -h /mnt/ssd 2>&1; echo "---"; df -h /media/jetson/nano-ssd 2>&1'
echo "=== samba password set for jetson? (check tdbsam) ==="
ssh $OPTS $N0 'sudo pdbedit -L -w 2>&1 | grep jetson || echo "no samba pw entry"'
echo DONE
