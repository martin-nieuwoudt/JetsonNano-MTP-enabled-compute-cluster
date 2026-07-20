#!/bin/bash
export CUDA_HOME=/usr/local/cuda
export CUDACXX=/usr/local/cuda/bin/nvcc
export PATH="/usr/local/cuda/bin:$PATH"
cd /home/jetson/llama.cpp
rm -rf build && mkdir build && cd build
CC=/usr/bin/gcc-10 CXX=/usr/bin/g++-10 cmake .. \
  -DBUILD_SHARED_LIBS=OFF \
  -DGGML_CUDA=ON \
  -DGGML_RPC=ON \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_ARCHITECTURES=53 \
  -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/gcc-8 \
  -DCMAKE_CUDA_STANDARD=14 \
  -DCMAKE_C_FLAGS="-march=armv8-a -mno-outline-atomics" \
  -DCMAKE_CXX_FLAGS="-march=armv8-a -mno-outline-atomics" \
  -DGGML_CUDA_FORCE_CUB=ON > /tmp/cmake_cfg.log 2>&1
echo "CFG_EXIT=$?"
tail -4 /tmp/cmake_cfg.log
