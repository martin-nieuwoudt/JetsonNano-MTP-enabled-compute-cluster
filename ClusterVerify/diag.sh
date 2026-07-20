#!/bin/bash
for i in $(seq 1 15); do [ -b /dev/sde1 ] && break; sleep 1; done
mkdir -p /mnt/card
mount -o rw /dev/sde1 /mnt/card
CARD=/mnt/card
echo "=== partition table of /dev/sde ==="
fdisk -l /dev/sde 2>&1 | head -40
echo "=== dpkg openssh ==="
chroot $CARD dpkg -l 2>/dev/null | grep -i openssh
echo "=== cached debs ==="
ls -la $CARD/var/cache/apt/archives/ 2>&1 | grep -i ssh
echo "=== any sshd anywhere on card ==="
find $CARD -name 'sshd' 2>/dev/null
echo "=== ssh.service symlink in wants ==="
ls -la $CARD/etc/systemd/system/multi-user.target.wants/ 2>&1 | grep -i ssh
echo "=== does /lib/systemd/system/ssh.service exist? ==="
ls -la $CARD/lib/systemd/system/ssh.service 2>&1
echo "=== /usr/sbin contents (ssh) ==="
ls $CARD/usr/sbin/ 2>&1 | grep -i ssh
echo "=== fstab on card ==="
cat $CARD/etc/fstab 2>&1
umount /mnt/card
echo DONE
