#!/bin/bash
cd /home/jetson/llama.cpp-mtp
echo "=== cpy_tensor signature + returns ==="
grep -n "ggml_backend_cuda_cpy_tensor\b\|ggml_backend_cuda_cpy_tensor(" ggml/src/ggml-cuda/ggml-cuda.cu | head
echo "--- cpy_tensor body returns ---"
awk '/ggml_backend_cuda_cpy_tensor\(/{f=1} f{print NR": "$0} f&&/^}/{c++; if(c>=1)exit}' ggml/src/ggml-cuda/ggml-cuda.cu | grep -n "return" | head
echo "=== should_fuse_mul_mat returns ==="
grep -n "ggml_cuda_should_fuse_mul_mat" ggml/src/ggml-cuda/ggml-cuda.cu | head
echo "=== block_reduce_policy returns ==="
grep -n "block_reduce_policy" ggml/src/ggml-cuda/ggml-cuda.cu | head
echo "=== lines 105-115 (error at 107,111) ==="
sed -n "100,115p" ggml/src/ggml-cuda/ggml-cuda.cu
echo "=== lines 405-415 (error at 410) ==="
sed -n "400,415p" ggml/src/ggml-cuda/ggml-cuda.cu
echo "=== lines 600-620 (error at 604,617) ==="
sed -n "598,620p" ggml/src/ggml-cuda/ggml-cuda.cu
