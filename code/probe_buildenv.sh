#!/bin/bash
# probe_buildenv.sh - check node0 build toolchain + existing llama.cpp source
ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=no jetson@192.168.50.150 '
echo "=== git ==="; which git && git --version
echo "=== cmake ==="; which cmake && cmake --version | head -1
echo "=== CUDA ==="; ls -d /usr/local/cuda* 2>/dev/null; /usr/local/cuda/bin/nvcc --version 2>/dev/null | tail -1
echo "=== g++ ==="; which g++ && g++ --version | head -1
echo "=== existing llama.cpp source ==="; ls -d /home/jetson/llama.cpp 2>/dev/null && (cd /home/jetson/llama.cpp && git log -1 --format="%H %ci" 2>/dev/null; git describe --tags 2>/dev/null)
echo "=== existing llama.cpp-mtp dir? ==="; ls -d /home/jetson/llama.cpp-mtp 2>/dev/null || echo NO_MTP_SRC
echo "=== internet? ==="; timeout 6 git ls-remote --heads https://github.com/ggml-org/llama.cpp.git 2>&1 | head -1 || echo NO_NET
'
