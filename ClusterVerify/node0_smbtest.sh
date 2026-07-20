#!/bin/bash
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N0=jetson@192.168.50.150
PW="${1:-jetson}"
echo "=== (re)set samba password (no -a, change existing) ==="
ssh $OPTS $N0 "echo -e '${PW}\n${PW}' | sudo smbpasswd -s jetson" 2>&1
echo "=== test auth locally via smbclient ==="
ssh $OPTS $N0 "echo '$PW' | smbclient -L //localhost/ssd -U jetson 2>&1 | head -20" 2>&1
echo DONE
