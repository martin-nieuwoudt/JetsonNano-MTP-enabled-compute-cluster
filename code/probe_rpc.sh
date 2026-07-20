#!/usr/bin/env bash
KEY=/home/marti/.ssh/id_ed25519
USER=jetson
for n in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$n"
  res=$(ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$USER@$ip" \
    "pgrep -af ggml-rpc-server >/dev/null 2>&1 && echo LISTENING || echo DOWN" 2>&1)
  echo "$ip  ->  $res"
done
