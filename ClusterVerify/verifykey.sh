#!/bin/bash
for i in $(seq 1 15); do [ -b /dev/sde1 ] && break; sleep 1; done
mkdir -p /mnt/card
mount -o rw /dev/sde1 /mnt/card
CARD=/mnt/card
echo "=== authorized_keys ==="
ls -l $CARD/home/jetson/.ssh/authorized_keys 2>&1
cat $CARD/home/jetson/.ssh/authorized_keys 2>&1 | head -1
echo "=== sudoers nopw ==="
ls -l $CARD/etc/sudoers.d/99-jetson-nopw 2>&1
echo "=== autologin getty ==="
grep -l autologin $CARD/etc/systemd/system/getty@tty1.service.d/*.conf 2>&1 || echo "no getty autologin"
echo "=== pubkey expected ==="
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHaOuIDZuZKy13grLsqKWzmkJHep37E4+xdZIjMfX5yQ marti@Martin-Asus"
umount /mnt/card
echo DONE
