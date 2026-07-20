#!/bin/bash
# Inspect the golden image read-only via loop + debugfs (no mount, no writes)
IMG=/mnt/c/ClusterVerify/Jetson_NanoZero_Baseline.img
OFF=14680064   # APP partition start: sector 28672 * 512

LOOP=$(losetup -f --show -o $OFF -r "$IMG" 2>/dev/null)
if [ -z "$LOOP" ]; then
  echo "losetup failed; trying without -r"
  LOOP=$(losetup -f --show -o $OFF "$IMG" 2>/dev/null)
fi
echo "LOOP DEVICE: $LOOP"
if [ -z "$LOOP" ]; then echo "COULD NOT ATTACH LOOP"; exit 1; fi

df() { # debugfs exists check: prints path + EXISTS/MISSING
  local p="$1"
  local r
  r=$(debugfs -R "stat $p" "$LOOP" 2>&1)
  if echo "$r" | grep -q "File not found"; then echo "MISSING   $p";
  else echo "PRESENT  $p"; fi
}

echo
echo "================ SERVICE BINARIES ================"
df /usr/sbin/sshd
df /usr/bin/ssh
df /usr/bin/dbus-daemon
df /usr/sbin/NetworkManager
df /usr/lib/policykit-1/polkitd
df /lib/systemd/systemd
df /usr/bin/tegrastats
df /usr/sbin/iptables

echo
echo "================ SSH CONFIG / UNITS ================"
df /etc/ssh/sshd_config
df /etc/ssh/ssh_config
df /lib/systemd/system/ssh.service
df /lib/systemd/system/sshd.service

echo
echo "================ D-BUS TOP LEVEL ================"
df /usr/share/dbus-1/system.conf
df /usr/share/dbus-1/session.conf

echo
echo "================ D-BUS system.d (count + validity) ================"
echo "--- listing system.d ---"
debugfs -R "ls -l /usr/share/dbus-1/system.d" "$LOOP" 2>&1 | awk '{print $NF}' | grep -v '^\.$' | grep -v '^\.\.$' | sort > /tmp/dbus_list.txt
wc -l < /tmp/dbus_list.txt | sed 's/^/system.d file count: /'
echo "--- first-byte (XML must be 3c = '<') for each ---"
while read f; do
  [ -z "$f" ] && continue
  b=$(debugfs -R "dump /usr/share/dbus-1/system.d/$f /dev/stdout" "$LOOP" 2>/dev/null | head -c 1 | xxd -p)
  printf "%s  %s\n" "$b" "$f"
done < /tmp/dbus_list.txt

echo
echo "================ NETWORK / NM ================"
df /etc/NetworkManager/NetworkManager.conf
df /usr/lib/NetworkManager/conf.d

echo
echo "================ INIT DEFAULT TARGET ================"
debugfs -R "cat /etc/systemd/system/default.target" "$LOOP" 2>/dev/null | head -c 200; echo

losetup -d "$LOOP" 2>/dev/null
echo DONE
