#!/usr/bin/env bash
# Copy launcher to each node and run it.
KEY=/home/marti/.ssh/id_ed25519
USER=jetson
SRC=/mnt/c/Users/marti/Desktop/Cluster/code/mtp_launcher.sh
for n in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$n"
  echo "===== $ip ====="
  scp -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$SRC" "$USER@$ip:/tmp/mtp_launcher.sh" 2>&1
  ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$USER@$ip" \
    "chmod +x /tmp/mtp_launcher.sh; /tmp/mtp_launcher.sh" 2>&1
done
echo "DONE"
