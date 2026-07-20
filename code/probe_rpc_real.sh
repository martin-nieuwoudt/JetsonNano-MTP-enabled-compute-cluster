#!/usr/bin/env bash
KEY=/home/marti/.ssh/id_ed25519
USER=jetson
for n in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$n"
  res=$(ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$USER@$ip" \
    "ss -ltnp 2>/dev/null | grep -q ':50052' && echo BOUND || echo NOT_BOUND; pgrep -af ggml-rpc-server | head -1" 2>&1)
  echo "$ip -> $res"
done
