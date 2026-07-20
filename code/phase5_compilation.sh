#!/bin/bash
# Phase 5: Targeted Compilation (Template Node)
# From: Nano Work Plan.md — Phase 5: Targeted Compilation (Template Node)
# Run on the template Jetson Nano via SSH

set -e

echo "[PHASE 5] Building hardware-specific RPC server binary with unified memory awareness..."

# Disk-space guard: NVCC build fails with spurious "No such file or directory"
# depfile errors when the SD is nearly full. Fail loudly instead of confusingly.
AVAIL_MB=$(df -m / | awk 'NR==2 {print $4}')
echo "[PHASE 5] Root fs free: ${AVAIL_MB} MB"
if [ "${AVAIL_MB:-0}" -lt 2048 ]; then
  echo "[PHASE 5] ERROR: less than 2 GB free on / — NVCC build will fail on disk-full." >&2
  echo "[PHASE 5] Free space or build on a larger volume (e.g. /mnt/ssd) before continuing." >&2
  exit 1
fi

# Critical: Do NOT mkdir build && cd build before calling cmake -B build
# That creates a nested build/build/ path breaking binary tracking

# CUDA toolchain must be on PATH for CMake to find nvcc (non-interactive SSH
# sessions do NOT source .bashrc, so /usr/local/cuda/bin is missing by default)
export CUDA_HOME=/usr/local/cuda
export CUDACXX=/usr/local/cuda/bin/nvcc
export CUDAHOSTCXX=/usr/bin/gcc-8
export PATH="/usr/local/cuda/bin:$PATH"

# Clone Repository (idempotent: reuse existing checkout on re-run)
if [ -d llama.cpp/.git ]; then
  echo "[PHASE 5] Existing llama.cpp repo found, reusing..."
  cd llama.cpp
else
  git clone https://github.com/ggml-org/llama.cpp.git && cd llama.cpp
fi

# Checkout Correct Commit
git stash && git checkout b56f079e2

# Apply NVCC 10.2 Compatibility Patches (required before cmake)
echo "[PHASE 5] Applying NVCC 10.2 compatibility patches (4 patches, b56f079e2)..."

# Patch 1: NVCC 10.2 rejects constexpr on __device__ variables
sed -i 's/static constexpr __device__ int8_t kvalues_iq4nl/static const __device__ int8_t kvalues_iq4nl/' ggml/src/ggml-cuda/common.cuh

# Patch 2: NVCC 10.2 lacks __builtin_assume -> use project's portable macro
sed -i 's/__builtin_assume(tid < D)/GGML_CUDA_ASSUME(tid < D)/' ggml/src/ggml-cuda/fattn-common.cuh

# Patch 3: same fix in fattn-vec-f16.cuh
sed -i 's/__builtin_assume(tid < D)/GGML_CUDA_ASSUME(tid < D)/' ggml/src/ggml-cuda/fattn-vec-f16.cuh

# Patch 4: same fix in fattn-vec-f32.cuh
sed -i 's/__builtin_assume(tid < D)/GGML_CUDA_ASSUME(tid < D)/' ggml/src/ggml-cuda/fattn-vec-f32.cuh

# Compile Binary (Maxwell SM 5.3, unified memory, RPC) — PROVEN RECIPE
# CRITICAL COMPILER SPLIT: host C/CXX = gcc-9 (provides vld1q_u8_x4 NEON intrinsic
# missing from gcc-8's arm_neon.h); nvcc pinned to gcc-8 via --compiler-bindir
# (nvcc 10.2 rejects gcc > 8).
echo "[PHASE 5] Compiling rpc-server..."
rm -rf build && /home/jetson/.local/bin/cmake -B build \
  -DGGML_CUDA=ON \
  -DGGML_RPC=ON \
  -DGGML_NATIVE=OFF \
  -DGGML_CPU_ARM_ARCH=armv8.1-a+nolse \
  -DCMAKE_CUDA_ARCHITECTURES=53 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_COMPILER=/usr/local/cuda-10.2/bin/nvcc \
  -DCMAKE_CUDA_FLAGS='--compiler-bindir /usr/bin/gcc-8' \
  -DCMAKE_C_COMPILER=gcc-9 \
  -DCMAKE_CXX_COMPILER=g++-9 \
  -DCMAKE_CUDA_STANDARD=14

cd build && make -j4

# Verify Binary (commit b56f079e2 builds it as 'rpc-server', no 'llama-' prefix)
./bin/rpc-server --help

echo "[PHASE 5] Compilation complete. Binary at ./bin/rpc-server"