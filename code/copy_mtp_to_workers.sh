#!/bin/bash
# copy_mtp_to_workers.sh - stage node0 b9886 bin dir locally, push to all 10 workers
set -e
LOCAL=/tmp/mtp_bin
rm -rf "$LOCAL"; mkdir -p "$LOCAL"
echo "=== pull bin dir from node0 ==="
scp -o BatchMode=yes -o ConnectTimeout=20 -o StrictHostKeyChecking=no \
  jetson@192.168.50.150:/home/jetson/llama.cpp-mtp/build/bin/* "$LOCAL/"
echo "staged: $(ls -1 "$LOCAL" | wc -l) files"
for ip in 151 152 153 154 155 156 157 158 159 160; do
  echo "=== worker .$ip ==="
  ssh -o BatchMode=yes -o ConnectTimeout=20 -o StrictHostKeyChecking=no jetson@192.168.50.$ip \
    'mkdir -p /home/jetson/llama.cpp-mtp/build/bin'
  scp -o BatchMode=yes -o ConnectTimeout=20 -o StrictHostKeyChecking=no \
    "$LOCAL"/* jetson@192.168.50.$ip:/home/jetson/llama.cpp-mtp/build/bin/
  echo "  copied"
done
echo "=== ALL WORKERS DONE ==="
