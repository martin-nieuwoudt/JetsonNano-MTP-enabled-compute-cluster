#!/bin/bash
# test_node0_mtp.sh - launch ggml-rpc-server (b9886) on node0 test port, verify it listens
ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=no jetson@192.168.50.150 bash -s <<'REMOTE'
pkill -f "ggml-rpc-server.*59999" 2>/dev/null
sleep 1
cd /home/jetson/llama.cpp-mtp/build/bin
nohup ./ggml-rpc-server --host 0.0.0.0 --port 59999 > /tmp/node0_mtp_test.log 2>&1 &
echo "launched_pid $!"
sleep 3
(ss -ltnp 2>/dev/null || netstat -ltnp 2>/dev/null) | grep 59999 || echo NOT_LISTENING
echo "---LOG---"
cat /tmp/node0_mtp_test.log
REMOTE
