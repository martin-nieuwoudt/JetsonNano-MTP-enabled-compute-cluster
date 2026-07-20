#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'bash -s' <<'EOF'
cd /home/jetson
pkill -f "ggml-rpc-server -H 0.0.0.0 -p 50053" 2>/dev/null
sleep 1
nohup /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server -H 0.0.0.0 -p 50053 -t 2 > /home/jetson/mtp_rpc.log 2>&1 &
echo "launch pid=$!"
sleep 4
echo "=== log ==="
cat /home/jetson/mtp_rpc.log
echo "=== listening? ==="
(ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null) | grep 50053
EOF
