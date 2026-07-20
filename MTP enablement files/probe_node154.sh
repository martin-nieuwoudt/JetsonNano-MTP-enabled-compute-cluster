#!/usr/bin/env bash
ssh -o BatchMode=yes jetson@192.168.50.154 bash -s <<'EOF'
set -e
echo "=== binary mtime ==="
stat -c '%y' /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server
echo "=== daemon self-test on alt port 50099 (8s) ==="
timeout 8 /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server -H 127.0.0.1 -p 50099 -t 2 > /tmp/self_test.log 2>&1 &
sleep 4
echo "--- self_test.log ---"
cat /tmp/self_test.log
echo "--- port check ---"
ss -ltnp 2>/dev/null | grep 50099 || echo "not listening"
echo "PROBE_DONE"
EOF
