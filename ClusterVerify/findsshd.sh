#!/bin/bash
for i in $(seq 1 15); do [ -b /dev/sde1 ] && break; sleep 1; done
mkdir -p /mnt/card
mount -o rw /dev/sde1 /mnt/card
echo "=== find sshd on card ==="
find $CARD -name sshd 2>/dev/null
echo "=== /usr/sbin/sshd? ==="
ls -l $CARD/usr/sbin/sshd 2>&1
echo "=== sshd unit ExecStart ==="
grep -r ExecStart $CARD/lib/systemd/system/ssh.service 2>&1
echo "=== openssh-server pkg files (if any) ==="
ls $CARD/usr/bin/ssh* $CARD/usr/sbin/ssh* 2>&1
umount /mnt/card
echo DONE
