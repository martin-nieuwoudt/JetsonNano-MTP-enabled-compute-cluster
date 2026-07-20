#!/bin/bash
# verify_worker_mtp.sh - launch ggml-rpc-server on a worker test port, verify listen
IP="${1:-151}"
ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=no jetson@192.168.50.$IP bash -s <<'REMOTE'
pkill -f "ggml-rpc-server.*59999" 2>/dev/null
sleep 1
cd /home/jetson/llama.cpp-mtp/build/bin
nohup ./ggml-rpc-server --host 0.0.0.0 --port 59999 > /tmp/worker_mtp_test.log 2>&1 &
echo "launched_pid $!"
sleep 3
(ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null) | grep 59999 || echo NOT_LISTENING
echo "---LOG---"; cat /tmp/worker_mtp_test.log
pkill -f "ggml-rpc-server.*59999" 2>/dev/null; echo "cleaned up"
REMOTE
