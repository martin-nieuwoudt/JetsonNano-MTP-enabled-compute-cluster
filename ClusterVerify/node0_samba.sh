#!/bin/bash
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N0=jetson@192.168.50.150
echo "=== hostname ==="; ssh $OPTS $N0 'hostname'
echo "=== SSD mounted? ==="; ssh $OPTS $N0 'lsblk | grep -i sd; echo "---"; mount | grep -i "ssd\|sda\|nvme" || echo "no ssd mount line"'
echo "=== samba installed? ==="; ssh $OPTS $N0 'which smbd nmbd 2>&1; dpkg -l | grep -i samba | head'
echo "=== smb.conf ==="; ssh $OPTS $N0 'cat /etc/samba/smb.conf 2>&1 | grep -v "^#" | grep -v "^;" | grep -v "^$"'
echo "=== samba users ==="; ssh $OPTS $N0 'sudo pdbedit -L 2>&1 || echo "pdbedit unavailable"'
echo "=== smbd running? ==="; ssh $OPTS $N0 'systemctl is-active smbd nmbd 2>&1; pgrep -a smbd || echo "no smbd"'
echo DONE
