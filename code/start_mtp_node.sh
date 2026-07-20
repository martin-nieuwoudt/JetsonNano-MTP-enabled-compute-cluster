#!/usr/bin/env bash
# Start MTP ggml-rpc-server detached on a single node via setsid (survives SSH logout).
KEY=/home/marti/.ssh/id_ed25519
USER=jetson
BIN=/home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server
ip="$1"
if [ -z "$ip" ]; then echo "usage: $0 <ip>"; exit 1; fi
ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$USER@$ip" \
  "pkill -f 'rpc-server' 2>/dev/null; sleep 1; setsid bash -c '$BIN -H 0.0.0.0 -p 50052 -t 4 >/tmp/ggml-rpc.log 2>&1' < /dev/null & echo launched pid \$!" 2>&1
sleep 2
ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$USER@$ip" \
  "ss -ltnp | grep ':50052' || echo NOT_LISTENING; pgrep -af ggml-rpc-server | head -1" 2>&1
