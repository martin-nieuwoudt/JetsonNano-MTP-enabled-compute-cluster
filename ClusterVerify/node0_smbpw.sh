#!/bin/bash
# Set a known Samba password for user 'jetson' on node0 (non-interactive).
# Password is passed via stdin to smbpasswd -s.
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N0=jetson@192.168.50.150
PW="${1:-cluster2026}"
echo "=== set samba password for jetson ==="
ssh $OPTS $N0 "echo -e '${PW}\n${PW}' | sudo smbpasswd -s -a jetson" 2>&1
echo "=== verify entry ==="
ssh $OPTS $N0 'sudo pdbedit -L | grep jetson' 2>&1
echo "=== restart smbd to be safe ==="
ssh $OPTS $N0 'sudo systemctl restart smbd nmbd 2>&1; systemctl is-active smbd' 2>&1
echo DONE
