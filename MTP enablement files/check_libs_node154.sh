#!/usr/bin/env bash
ssh -o BatchMode=yes jetson@192.168.50.154 bash -s <<'EOF'
echo "=== running daemon pid ==="
PID=$(pgrep -f 'ggml-rpc-server.*50052' | head -1)
echo "pid=$PID"
echo "=== loaded shared libs ==="
cat /proc/$PID/maps 2>/dev/null | grep -E 'libggml|ggml-rpc-server' | awk '{print $6}' | sort -u
echo "=== bin dir .so listing ==="
ls -la /home/jetson/llama.cpp-mtp/build/bin/*.so* 2>&1
echo "=== ldd on daemon ==="
ldd /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server 2>&1 | grep -i ggml
EOF
