#!/bin/bash
set -e
for i in $(seq 1 15); do [ -b /dev/sde1 ] && break; sleep 1; done
mkdir -p /mnt/card
mount -o rw /dev/sde1 /mnt/card

echo "=== 1. Console autologin (no login prompt) ==="
# Create the getty override for tty1 -> autologin jetson
mkdir -p /mnt/card/etc/systemd/system/getty@tty1.service.d
cat > /mnt/card/etc/systemd/system/getty@tty1.service.d/autologin.conf <<'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin jetson --noclear %I $TERM
EOF
# Also serial/console autologin (Jetson often uses ttyS0 / ttyTCU0)
for t in ttyS0 ttyTCU0 serial-getty@ttyS0.service.d serial-getty@ttyTCU0.service.d; do :; done
mkdir -p /mnt/card/etc/systemd/system/serial-getty@ttyS0.service.d
cat > /mnt/card/etc/systemd/system/serial-getty@ttyS0.service.d/autologin.conf <<'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin jetson --noclear -s %I 115200,38400,9600
EOF
mkdir -p /mnt/card/etc/systemd/system/serial-getty@ttyTCU0.service.d
cat > /mnt/card/etc/systemd/system/serial-getty@ttyTCU0.service.d/autologin.conf <<'EOF'
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin jetson --noclear -s %I 115200,38400,9600
EOF

echo "=== 2. Passwordless sudo for jetson ==="
cat > /mnt/card/etc/sudoers.d/99-jetson-nopw <<'EOF'
jetson ALL=(ALL) NOPASSWD: ALL
EOF
chmod 440 /mnt/card/etc/sudoers.d/99-jetson-nopw

echo "=== 3. Install SSH public key ==="
mkdir -p /mnt/card/home/jetson/.ssh
cat > /mnt/card/home/jetson/.ssh/authorized_keys <<'EOF'
ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIHaOuIDZuZKy13grLsqKWzmkJHep37E4+xdZIjMfX5yQ marti@Martin-Asus
EOF
chmod 700 /mnt/card/home/jetson/.ssh
chmod 600 /mnt/card/home/jetson/.ssh/authorized_keys
# fix ownership (uid 1000 is jetson on the image)
chown -R 1000:1000 /mnt/card/home/jetson/.ssh 2>/dev/null || true

echo "=== 4. Confirm ssh.service enabled ==="
ls -l /mnt/card/etc/systemd/system/multi-user.target.wants/ssh.service 2>&1

umount /mnt/card
echo DONE
