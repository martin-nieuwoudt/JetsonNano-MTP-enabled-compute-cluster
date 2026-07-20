#!/bin/bash
# build_node0_mtp.sh - configure + build ggml-rpc-server from b9886 on node0
# MATCHES the proven stable build: GGML_CUDA=OFF (CPU-only, avoids CUDA10.2/GCC conflict)
# Logs to /tmp/node0_mtp_build.log
ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=no jetson@192.168.50.150 '
set -e
cd /home/jetson/llama.cpp-mtp
rm -rf build
mkdir -p build && cd build
echo "=== cmake configure (CPU-only, RDMA off, matching stable build) ===" | tee /tmp/node0_mtp_build.log
cmake -DGGML_CUDA=OFF -DGGML_RPC_RDMA=OFF -DCMAKE_BUILD_TYPE=Release -DGGML_RPC=ON .. >> /tmp/node0_mtp_build.log 2>&1
echo "CMAKE_EXIT=$?" | tee -a /tmp/node0_mtp_build.log
echo "=== build ggml-rpc-server ===" | tee -a /tmp/node0_mtp_build.log
cmake --build . --target ggml-rpc-server --parallel "$(nproc)" >> /tmp/node0_mtp_build.log 2>&1
echo "BUILD_EXIT=$?" | tee -a /tmp/node0_mtp_build.log
ls -la bin/ggml-rpc-server 2>/dev/null && echo BUILT_OK || echo BUILT_FAIL
'
