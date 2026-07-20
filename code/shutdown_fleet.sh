#!/usr/bin/env bash
# Graceful fleet shutdown. Workers first, node0 (USB SSD) last.
KEY=/home/marti/.ssh/id_ed25519
USER=jetson
NODES="151 152 153 154 155 156 157 158 159 160 150"
for n in $NODES; do
  ip="192.168.50.$n"
  echo "==> shutting down $ip =="
  ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$USER@$ip" \
    "sudo shutdown -h now" 2>&1 || echo "   (ssh failed or already down: $ip)"
  sleep 1
done
echo "DONE: shutdown signals sent to all 11 nodes."
