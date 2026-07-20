#!/usr/bin/env bash
# Start the MTP RPC server via systemd (boot-persistent, survives SSH logout,
# Restart=on-failure). Use this instead of setsid/nohup which die on disconnect.
KEY=/home/marti/.ssh/id_ed25519
USER=jetson
for n in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$n"
  echo "===== $ip ====="
  ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$USER@$ip" \
    "sudo systemctl restart llama-rpc.service 2>&1; sleep 2; ss -ltnp | grep ':50052' || echo NOT_LISTENING; pgrep -af ggml-rpc-server | head -1" 2>&1
done
echo "DONE"
