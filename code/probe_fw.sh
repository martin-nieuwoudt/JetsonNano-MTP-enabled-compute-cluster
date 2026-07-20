#!/usr/bin/env bash
KEY=/home/marti/.ssh/id_ed25519
USER=jetson
for n in 150 159; do
  ip="192.168.50.$n"
  echo "===== NODE $ip ====="
  ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$USER@$ip" \
    "echo '--- ufw status ---'; sudo ufw status 2>/dev/null || echo 'no ufw'; echo '--- iptables ---'; sudo iptables -L -n 2>/dev/null | head -30; echo '--- nft ---'; sudo nft list ruleset 2>/dev/null | head -20" 2>&1
done
