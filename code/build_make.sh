#!/bin/bash
# Build wrapper: runs make in the already-configured build dir.
# CUDA must be on PATH for nvcc (non-interactive SSH skips .bashrc).
export CUDA_HOME=/usr/local/cuda
export CUDACXX=/usr/local/cuda/bin/nvcc
export PATH="/usr/local/cuda/bin:$PATH"
cd /home/jetson/llama.cpp/build
cmake --build . --parallel "$(nproc)" > /tmp/phase5_build.log 2>&1
echo "BUILD_EXIT=$?"
tail -6 /tmp/phase5_build.log
