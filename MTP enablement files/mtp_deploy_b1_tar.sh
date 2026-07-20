#!/bin/bash
# Step 1: tar the MTP worker binary + its .so libs on node0
ssh -o BatchMode=yes jetson@192.168.50.150 'bash -s' <<'EOF'
set -e
cd /home/jetson/llama.cpp-mtp/build/bin
tar czf /tmp/mtp_worker.tgz \
  ggml-rpc-server \
  libggml-base.so.0.15.3 \
  libggml-cpu.so.0.15.3 \
  libggml-cuda.so.0.15.3 \
  libggml-rpc.so.0.15.3 \
  libggml.so.0.15.3
ls -l /tmp/mtp_worker.tgz
echo "TAR OK"
EOF
