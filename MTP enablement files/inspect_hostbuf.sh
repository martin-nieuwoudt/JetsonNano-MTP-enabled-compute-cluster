#!/bin/bash
cd /home/jetson/llama.cpp-mtp
F=ggml/src/ggml-cuda/ggml-cuda.cu
echo "=== register_host_buffer (search) ==="
grep -n "ggml_backend_cuda_register_host_buffer" "$F"
echo "=== unregister_host_buffer (search) ==="
grep -n "ggml_backend_cuda_unregister_host_buffer" "$F"
echo
echo "=== full register_host_buffer body ==="
awk '/ggml_backend_cuda_register_host_buffer\(/{f=1} f{print NR": "$0} f&&/^}/{exit}' "$F"
echo
echo "=== full unregister_host_buffer body ==="
awk '/ggml_backend_cuda_unregister_host_buffer\(void/{f=1} f{print NR": "$0} f&&/^}/{exit}' "$F"
