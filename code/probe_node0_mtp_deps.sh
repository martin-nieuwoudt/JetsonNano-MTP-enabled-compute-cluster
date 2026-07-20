#!/bin/bash
# probe_node0_mtp_deps.sh - kill test server, check binary deps + sibling libs
ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=no jetson@192.168.50.150 bash -s <<'REMOTE'
pkill -f "ggml-rpc-server.*59999" 2>/dev/null; echo "test server killed"
cd /home/jetson/llama.cpp-mtp/build/bin
echo "=== ldd ggml-rpc-server ==="
ldd ggml-rpc-server
echo "=== bin dir contents ==="
ls -la
REMOTE
