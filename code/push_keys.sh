#!/usr/bin/env bash
# Bootstrap id_ed25519.pub onto all 11 Jetson nodes (new image, password auth).
# Run via: wsl -d Ubuntu -e bash /mnt/c/Users/marti/Desktop/Cluster/code/push_keys.sh
#
# Loops 192.168.50.150 .. 192.168.50.160 (node0 + workers 1..10).
# Idempotent: appends the pubkey only if not already present (guards against
# duplicate lines on re-runs). Requires password auth to be ON at first boot
# (the fresh/worker image ships with PasswordAuthentication yes + jetson/jetson).
set -u
export SSHPASS='jetson'
PUB="$(cat /mnt/c/Users/marti/.ssh/id_ed25519.pub)"
PUB_B64="$(echo "$PUB" | cut -d' ' -f2)"
for i in $(seq 150 160); do
  ip="192.168.50.$i"
  echo "== $ip =="
  sshpass -e ssh \
    -o StrictHostKeyChecking=accept-new \
    -o UserKnownHostsFile=/mnt/c/Users/marti/.ssh/known_hosts \
    -o ConnectTimeout=15 \
    "jetson@$ip" \
    "mkdir -p ~/.ssh && chmod 700 ~/.ssh && grep -q '$PUB_B64' ~/.ssh/authorized_keys 2>/dev/null || echo '$PUB' >> ~/.ssh/authorized_keys; chmod 600 ~/.ssh/authorized_keys && echo KEY_INSTALLED" 2>&1
done
echo "DONE"
