#!/usr/bin/env bash
KEY=/home/marti/.ssh/id_ed25519
USER=jetson
ip="192.168.50.150"
ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$USER@$ip" bash <<'EOF'
echo "=== systemd rpc services ==="
systemctl list-unit-files 2>/dev/null | grep -i rpc
ls -la /etc/systemd/system/ 2>/dev/null | grep -i rpc
echo "=== rc.local ==="
cat /etc/rc.local 2>/dev/null || echo "no rc.local"
echo "=== crontab @reboot ==="
crontab -l 2>/dev/null | grep -i reboot || echo "no @reboot in user crontab"
sudo crontab -l 2>/dev/null | grep -i reboot || echo "no @reboot in root crontab"
echo "=== /etc/cron.d ==="
grep -rl rpc /etc/cron.d/ 2>/dev/null || echo "none in cron.d"
echo "=== profile / bashrc refs ==="
grep -l rpc /home/jetson/.bashrc /home/jetson/.profile /etc/profile 2>/dev/null || echo "none in shell profiles"
echo "=== any rpc start scripts ==="
ls -la /home/jetson/*.sh 2>/dev/null | grep -i rpc
ls -la /usr/local/bin/ 2>/dev/null | grep -i rpc
EOF
