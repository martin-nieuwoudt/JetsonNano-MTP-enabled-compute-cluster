#!/bin/bash
# Regenerate node2 ssh host keys in-session (no reboot).
# The image's sshd does NOT auto-run ssh-keygen -A on boot, so keys must
# exist before any reboot or SSH breaks. ssh-keygen -A fails on this image
# with "hostname contains invalid characters" (live hostname quirk), so we
# generate each key type explicitly with a fixed -C comment.
KEY=/home/marti/.ssh/id_ed25519_vm
OPTS="-i $KEY -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N2=jetson@192.168.50.152

ssh $OPTS $N2 'bash -s' <<'PAYLOAD'
set -e
echo "=== before ==="
ls /etc/ssh/ | grep ssh_host_ || echo "NONE"
sudo rm -f /etc/ssh/ssh_host_*
sudo ssh-keygen -t ed25519 -f /etc/ssh/ssh_host_ed25519_key -N "" -C "nano02" >/dev/null
sudo ssh-keygen -t rsa -b 4096 -f /etc/ssh/ssh_host_rsa_key -N "" -C "nano02" >/dev/null
sudo ssh-keygen -t ecdsa -b 521 -f /etc/ssh/ssh_host_ecdsa_key -N "" -C "nano02" >/dev/null
sudo ssh-keygen -t ed25519 -f /etc/ssh/ssh_host_ed25519_key -N "" -C "nano02" >/dev/null 2>&1 || true
echo "=== after ==="
ls /etc/ssh/ | grep ssh_host_
echo "machine-id: $(cat /etc/machine-id)"
echo "hostname: $(hostname)"
PAYLOAD
echo DONE
