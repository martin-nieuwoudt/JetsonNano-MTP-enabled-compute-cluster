#!/usr/bin/env bash
# Test .157 with a -t 2 worker on a test port to see if -t 4 is the culprit
ip=192.168.50.157
ssh -o BatchMode=yes "jetson@$ip" 'bash -s' <<'EOF'
set -e
cd /home/jetson/llama.cpp-mtp/build/bin
pkill -f "50099" 2>/dev/null || true
sleep 1
nohup ./ggml-rpc-server -H 127.0.0.1 -p 50099 -t 2 >/tmp/rpc_t2.log 2>&1 &
sleep 3
echo "=== proc ==="
pgrep -af "50099" | head -1 || echo "NOT RUNNING"
echo "=== log ==="
tail -8 /tmp/rpc_t2.log
EOF
