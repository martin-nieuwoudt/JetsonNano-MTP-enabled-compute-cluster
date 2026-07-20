#!/bin/bash
cd /home/jetson/llama.cpp-mtp
F=ggml/src/ggml-cuda/ggml-cuda.cu
echo "=== any macro override of GGML_STATUS_SUCCESS in whole tree? ==="
grep -rn "define GGML_STATUS_SUCCESS" . 2>/dev/null | head
echo "(empty above = no macro)"
echo
echo "=== declarations of the 'enum' functions that still error ==="
grep -n "^enum ggml_status ggml_cuda_set_device\|^static enum ggml_status ggml_backend_cuda_buffer_init_tensor\|^static enum ggml_status ggml_backend_cuda_split_buffer_init_tensor\|^static enum ggml_status ggml_cuda_mul_mat_id\|^static enum ggml_status ggml_backend_cuda_graph_compute" "$F"
echo
echo "=== is ggml_cuda_set_device declared void anywhere (header)? ==="
grep -rn "ggml_cuda_set_device" ggml/src/ggml-cuda/*.h ggml/include/*.h 2>/dev/null | head
echo
echo "=== split_buffer_init_tensor decl (around 860-880) ==="
sed -n "858,878p" "$F"
echo
echo "=== graph_compute decl (3925) + first return ==="
sed -n "3925,3935p" "$F"
