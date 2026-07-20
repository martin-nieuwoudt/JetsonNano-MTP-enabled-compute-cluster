#!/bin/bash
cd /home/jetson/llama.cpp-mtp
for L in 3975 3981 4020 4027 4034 4315 4322; do
  echo "=== ggml-cuda.cu:$L ==="
  sed -n "$((L-4)),$((L+2))p" ggml/src/ggml-cuda/ggml-cuda.cu
done
echo "=== grep return-type funcs near 3981/4027/4034/4322 ==="
grep -n "ggml_backend_cuda_graph_optimize\|ggml_cuda_mul_mat_id\|ggml_backend_cuda_buffer_interface\|ggml_backend_cuda_split_buffer_interface" ggml/src/ggml-cuda/ggml-cuda.cu | head -40
