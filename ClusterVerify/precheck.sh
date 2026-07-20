#!/bin/bash
for i in $(seq 1 15); do [ -b /dev/sde1 ] && break; sleep 1; done
mkdir -p /mnt/card
mount -o rw /dev/sde1 /mnt/card
CARD=/mnt/card
echo "=== fstab ==="
cat $CARD/etc/fstab 2>&1
echo "=== cached openssh-server deb ==="
ls -la $CARD/var/cache/apt/archives/openssh-server*.deb 2>&1
echo "=== cached deps (openssh-sftp-server, openssh-client) ==="
ls -la $CARD/var/cache/apt/archives/openssh-sftp-server*.deb $CARD/var/cache/apt/archives/openssh-client*.deb 2>&1
echo "=== /usr/sbin/sshd after potential prior attempts ==="
ls -la $CARD/usr/sbin/sshd 2>&1
echo "=== ssh.service in wants ==="
ls -la $CARD/etc/systemd/system/multi-user.target.wants/ 2>&1 | grep -i ssh
echo "=== existing selfheal? ==="
ls -la $CARD/usr/local/bin/cluster-selfheal.sh $CARD/etc/systemd/system/cluster-selfheal.service 2>&1
umount /mnt/card
echo DONE
