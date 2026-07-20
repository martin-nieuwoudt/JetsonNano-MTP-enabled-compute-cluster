#!/bin/bash
set -e
for i in $(seq 1 15); do [ -b /dev/sde1 ] && break; sleep 1; done
mkdir -p /mnt/card
mount -o rw /dev/sde1 /mnt/card
CARD=/mnt/card
echo "=== 1. sshd binary location ==="
ls -l $CARD/usr/sbin/sshd 2>&1
echo "=== 2. ssh.service ExecStart ==="
grep -h ExecStart $CARD/lib/systemd/system/ssh.service 2>&1 || echo "no ssh.service unit file found"
echo "=== 3. host keys present? ==="
ls $CARD/etc/ssh/ssh_host_*_key 2>&1 || echo "NO HOST KEYS"

# Safety: if unit expects /usr/bin/sshd but binary is /usr/sbin/sshd, symlink it
UNIT_ES=$(grep -h '^ExecStart' $CARD/lib/systemd/system/ssh.service 2>/dev/null | head -1)
if echo "$UNIT_ES" | grep -q '/usr/bin/sshd' && [ -x $CARD/usr/sbin/sshd ] && [ ! -e $CARD/usr/bin/sshd ]; then
  ln -sf /usr/sbin/sshd $CARD/usr/bin/sshd
  echo "symlinked /usr/bin/sshd -> /usr/sbin/sshd"
fi

echo "=== 4. generate host keys (offline, chroot) ==="
if ! ls $CARD/etc/ssh/ssh_host_*_key >/dev/null 2>&1; then
  chroot $CARD /usr/bin/ssh-keygen -A 2>&1 || echo "chroot ssh-keygen failed, trying direct"
  if ! ls $CARD/etc/ssh/ssh_host_*_key >/dev/null 2>&1; then
    for t in rsa ed25519 ecdsa; do
      $CARD/usr/bin/ssh-keygen -t $t -f $CARD/etc/ssh/ssh_host_${t}_key -N "" -q 2>&1 || true
    done
  fi
fi
ls $CARD/etc/ssh/ssh_host_*_key 2>&1

echo "=== 5. write self-heal script ==="
cat > $CARD/usr/local/bin/cluster-selfheal.sh <<'EOF'
#!/bin/bash
# cluster-selfheal: guarantee host keys, sshd, and network on boot
# Runs as a oneshot systemd service (After=ssh.service) and is idempotent.

if ! ls /etc/ssh/ssh_host_*_key >/dev/null 2>&1; then
  /usr/bin/ssh-keygen -A 2>/dev/null
fi

if ! pgrep -x sshd >/dev/null 2>&1; then
  /usr/sbin/sshd 2>/dev/null || /usr/bin/sshd 2>/dev/null
fi

nmcli con up "Wired connection 1" >/dev/null 2>&1 || true
if ! ip addr show eth0 | grep -q 'inet '; then
  ip link set eth0 up 2>/dev/null
  udhcpc -i eth0 -n -q 2>/dev/null || dhclient eth0 2>/dev/null || true
fi
if ! ip addr show eth0 | grep -q 'inet '; then
  ip addr add 192.168.50.151/24 dev eth0 2>/dev/null
  ip route add default via 192.168.50.1 2>/dev/null || true
fi
EOF
chmod 755 $CARD/usr/local/bin/cluster-selfheal.sh

echo "=== 6. write self-heal service ==="
cat > $CARD/etc/systemd/system/cluster-selfheal.service <<'EOF'
[Unit]
Description=Cluster node self-heal (host keys, sshd, network)
After=network.target ssh.service
Wants=network.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/bin/cluster-selfheal.sh

[Install]
WantedBy=multi-user.target
EOF
ln -sf /etc/systemd/system/cluster-selfheal.service $CARD/etc/systemd/system/multi-user.target.wants/cluster-selfheal.service

echo "=== 7. ensure ssh.service enabled ==="
ln -sf /lib/systemd/system/ssh.service $CARD/etc/systemd/system/multi-user.target.wants/ssh.service

echo "=== 8. set static .151 nmconnection (node1) ==="
CONN_DIR=$CARD/etc/NetworkManager/system-connections
mkdir -p $CONN_DIR
cat > $CONN_DIR/"Wired connection 1.nmconnection" <<'EOF'
[connection]
id=Wired connection 1
uuid=00000000-0000-0000-0000-000000000001
type=ethernet
autoconnect=true
interface-name=eth0

[ethernet]
mac-address-blacklist=

[ipv4]
method=manual
address1=192.168.50.151/24,192.168.50.1
dns=192.168.50.1;
ignore-auto-dns=true

[ipv6]
method=disabled
EOF
chmod 600 $CONN_DIR/"Wired connection 1.nmconnection"

echo "=== 9. verify enabled units ==="
ls -l $CARD/etc/systemd/system/multi-user.target.wants/ | grep -E 'ssh|selfheal'

echo "=== 10. verify sshd path + keys + selfheal present ==="
ls -l $CARD/usr/sbin/sshd $CARD/usr/local/bin/cluster-selfheal.sh
ls $CARD/etc/ssh/ssh_host_*_key 2>&1

umount /mnt/card
echo DONE
