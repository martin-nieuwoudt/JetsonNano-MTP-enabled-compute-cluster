#!/bin/bash
# probe_gcc.sh - find available GCC and how stable build was configured
ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=no jetson@192.168.50.150 '
echo "=== available gcc/g++ ==="; ls /usr/bin/gcc* /usr/bin/g++* 2>/dev/null
echo "=== gcc-8 present? ==="; which gcc-8 g++-8 2>/dev/null || echo NO_GCC8
echo "=== stable build CMakeCache compiler ==="; grep -E "CMAKE_C_COMPILER:|CMAKE_CXX_COMPILER:|CUDA_HOST_COMPILER|CMAKE_CUDA_COMPILER:" /home/jetson/llama.cpp/build/CMakeCache.txt 2>/dev/null
echo "=== stable build CUDA arch ==="; grep -iE "CUDA_ARCH|GGML_CUDA" /home/jetson/llama.cpp/build/CMakeCache.txt 2>/dev/null | head
'
