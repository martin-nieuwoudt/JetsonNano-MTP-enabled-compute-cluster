#!/bin/bash
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N1=jetson@192.168.50.151
echo "=== mount state of / ==="
ssh $OPTS $N1 'mount | grep " on / "'; echo
echo "=== dmesg ext4 errors (last 20) ==="
ssh $OPTS $N1 'sudo dmesg 2>/dev/null | grep -i ext4 | tail -20'; echo
echo "=== dmesg structure needs cleaning ==="
ssh $OPTS $N1 'sudo dmesg 2>/dev/null | grep -i "structure needs cleaning" | tail -5'; echo
echo "=== touch test in /tmp (writable?) ==="
ssh $OPTS $N1 'touch /tmp/_wtest 2>&1 && echo TMP_WRITABLE && rm -f /tmp/_wtest'; echo
echo "=== touch test in /usr/share/dbus-1/system.d (writable?) ==="
ssh $OPTS $N1 'touch /usr/share/dbus-1/system.d/_wtest 2>&1 && echo DST_WRITABLE && rm -f /usr/share/dbus-1/system.d/_wtest || echo DST_WRITE_FAIL'; echo
echo DONE
