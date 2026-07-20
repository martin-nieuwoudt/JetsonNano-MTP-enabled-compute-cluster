#!/bin/bash
cd /home/jetson/llama.cpp-mtp
F=ggml/src/ggml-cuda/mmq.cu
echo "=== mmq.cu 278-310 (file line numbers via grep -n) ==="
grep -n "" "$F" | sed -n '278,310p'
echo
echo "=== function signature containing this region ==="
awk 'NR<=305 && /bool ggml_cuda_should_use_mmq|ggml_cuda_should_use_mmq\(/{print NR": "$0}' "$F"
