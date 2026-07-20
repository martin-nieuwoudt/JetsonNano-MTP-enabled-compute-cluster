#!/bin/bash
set -e
export CUDA_HOME=/usr/local/cuda
export CUDACXX=/usr/local/cuda/bin/nvcc
export PATH="/usr/local/cuda/bin:$PATH"
export CUDAHOSTCXX=/usr/bin/gcc-8
echo "== nvcc now on PATH? =="
which nvcc
echo "== nvcc identify with CUDAHOSTCXX=gcc-8 =="
echo 'int main(){}' > /tmp/t.cu
nvcc /tmp/t.cu -o /tmp/t.out 2>&1 | head -5; echo "nvcc-exit:$?"
echo "== throwaway cmake configure test =="
cd ~/llama.cpp
rm -rf /tmp/cfgtest && mkdir /tmp/cfgtest && cd /tmp/cfgtest
CC=/usr/bin/gcc-10 CXX=/usr/bin/g++-10 cmake ~/llama.cpp \
  -DGGML_CUDA=ON -DGGML_RPC=ON -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_ARCHITECTURES=53 -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/gcc-8 \
  -DCMAKE_CUDA_STANDARD=14 \
  -DCMAKE_C_FLAGS="-march=armv8-a -mno-outline-atomics" \
  -DCMAKE_CXX_FLAGS="-march=armv8-a -mno-outline-atomics" \
  -DGGML_CUDA_FORCE_CUB=ON 2>&1 | grep -iE "CUDA compiler identification|Configuring done|No CMAKE_CUDA_COMPILER|error" | head -10
