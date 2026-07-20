#!/bin/bash
cd /home/jetson
echo "=== STABLE reference mmq.cu: ggml_cuda_should_use_mmq ==="
R=llama.cpp/ggml/src/ggml-cuda/mmq.cu
M=llama.cpp-mtp/ggml/src/ggml-cuda/mmq.cu
if [ -f "$R" ]; then
  awk '/bool ggml_cuda_should_use_mmq\(/{f=1} f{print NR": "$0} f&&/^}/{c++; if(c>=1 && $0=="}"){exit}}' "$R" | head -40
else
  echo "stable mmq.cu NOT FOUND"
fi
echo
echo "=== MTP version same region (265-310) ==="
sed -n '265,310p' "$M"
