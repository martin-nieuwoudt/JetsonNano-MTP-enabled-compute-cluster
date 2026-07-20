#!/bin/bash
# switch_fleet_mtp.sh - stop old rpc-server, start b9886 ggml-rpc-server on :50052
BIN=/home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server
for ip in 150 151 152 153 154 155 156 157 158 159 160; do
  echo "=== node .$ip ==="
  ssh -o BatchMode=yes -o ConnectTimeout=20 -o StrictHostKeyChecking=no jetson@192.168.50.$ip bash -s <<REMOTE 2>/dev/null || echo "  SSH_FAIL"
# stop old stable rpc-server (any on 50052)
pkill -f "rpc-server --host" 2>/dev/null
pkill -f "llama.cpp/build/bin/rpc-server" 2>/dev/null
sleep 1
# start new MTP server
cd /home/jetson/llama.cpp-mtp/build/bin
nohup ./ggml-rpc-server --host 0.0.0.0 --port 50052 -t 4 > /tmp/ggml_rpc_server.log 2>&1 &
echo "  started pid \$!"
sleep 2
(ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null) | grep 50052 || echo "  PORT_50052_NOT_LISTENING"
REMOTE
done
echo "=== FLEET SWITCH DONE ==="
