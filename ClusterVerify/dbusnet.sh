#!/bin/bash
ssh -i /root/.ssh/id_ed25519 \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ConnectTimeout=10 -o BatchMode=yes \
  jetson@192.168.50.151 \
  'echo "=== default route ==="; ip route | head -3
echo "=== DNS resolve test ==="; getent hosts archive.ubuntu.com 2>&1 || echo "no DNS"
echo "=== apt cache dbus deb? ==="; ls -l /var/cache/apt/archives/*.deb 2>/dev/null | grep -i dbus || echo "no dbus deb cached"
echo "=== dpkg dbus version ==="; dpkg-query -W -f="\${Version}\n" dbus 2>/dev/null
echo "=== can we reach apt? (5s) ==="; timeout 5 bash -c "cat < /dev/null > /dev/tcp/archive.ubuntu.com/80" 2>&1 && echo "TCP 80 OK" || echo "TCP 80 FAIL"
echo "=== messagebus user exists? ==="; id messagebus 2>&1 || echo "no messagebus user"'
