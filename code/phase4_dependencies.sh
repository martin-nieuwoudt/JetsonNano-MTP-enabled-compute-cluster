#!/bin/bash
# Phase 4: Software Dependencies Installation (Template Node)
# From: Nano Work Plan.md — Phase 4: Software Dependencies (Template Node)
# Run on the template Jetson Nano via SSH

set -e

echo "[PHASE 4] Installing software dependencies for Maxwell compilation..."

# Package Update
sudo apt update && sudo apt upgrade -y

# Compiler Chain
# NOTE: Mixed GCC toolchain is REQUIRED for the proven Maxwell build:
#   gcc-10/g++-10 = host compiler (Phase 5 sets CC/CXX to these)
#   gcc-8/g++-8   = CUDA 10.2 NVCC host compiler (CMAKE_CUDA_HOST_COMPILER)
sudo apt install -y build-essential cmake git pkg-config libopenblas-dev liblapack-dev
sudo apt install -y gcc-10 g++-10 gcc-8 g++-8

# Route generic gcc/g++ to version 10 (CUDA host compiler stays gcc-8, set explicitly in cmake)
sudo update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-10 100
sudo update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-10 100
sudo ln -sf /usr/bin/gcc-10 /usr/bin/gcc
sudo ln -sf /usr/bin/g++-10 /usr/bin/g++

# Entropy Daemon
sudo apt install -y haveged
sudo systemctl enable haveged

# NFS Client (all nodes need this)
sudo apt install -y nfs-common

# CMake 3.18+ REQUIRED by llama.cpp commit 667d72846 (ggml-cuda/CMakeLists.txt:1)
# Ubuntu 20.04 apt only ships cmake 3.16.3 -> configure fails immediately.
# Install a newer CMake via pip (most reliable path on arm64).
sudo apt install -y python3-pip
pip3 install --user cmake
# NOTE: resolve the pip bin dir ON THE JETSON (not via Windows shell expansion)
PIP_BIN="$(python3 -m site --user-base)/bin"
sudo ln -sf "$PIP_BIN/cmake" /usr/local/bin/cmake
hash -r
echo "[PHASE 4] CMake version now: $(cmake --version | head -1)"

echo "[PHASE 4] Software dependencies installed successfully."