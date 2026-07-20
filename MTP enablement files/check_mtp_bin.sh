#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'bash -s' <<'EOF'
echo "=== MTP worker binary on disk? ==="
ls -l /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server 2>&1 || echo "MISSING"
echo "=== MTP libs? ==="
ls -l /home/jetson/llama.cpp-mtp/build/bin/*.so* 2>&1 | head
echo "=== stable worker binary (for comparison) ==="
ls -l /home/jetson/llama.cpp/build/bin/rpc-server 2>&1 || echo "MISSING"
echo "=== any MTP worker running? ==="
pgrep -af ggml-rpc-server || echo "none running"
EOF
