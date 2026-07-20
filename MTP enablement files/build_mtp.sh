set -e
cd /home/jetson/llama.cpp-mtp
echo "BUILD START $(date)"
rm -rf build
/home/jetson/.local/bin/cmake -B build \
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
  -DCMAKE_CUDA_STANDARD=14 \
  -DGGML_CUDA_FA=OFF \
  -DGGML_CUDA_GRAPHS=OFF \
  -DGGML_RPC_RDMA=OFF \
  -DGGML_CUDA_NCCL=OFF 2>&1 | tail -20
echo "=== CONFIGURE DONE, building ggml-rpc-server ==="
cd build && make -j4 ggml-rpc-server 2>&1 | tail -80
echo "BUILD END $(date)  EXIT=${PIPESTATUS[0]}"
ls -la bin/ggml-rpc-server 2>&1
