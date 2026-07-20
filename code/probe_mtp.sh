#!/usr/bin/env bash
KEY=/home/marti/.ssh/id_ed25519
USER=jetson
ip="192.168.50.150"
echo "=== MTP binary present? ==="
ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$USER@$ip" \
  "ls -l /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server 2>&1; echo '--- current daemon cmdline ---'; pgrep -af rpc-server | head -1" 2>&1
