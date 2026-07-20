#!/bin/bash
cd /home/jetson/llama.cpp-mtp
F=ggml/src/ggml-cuda/ggml-cuda.cu
echo "=== cat -A 4296-4325 (show tabs as ^I) ==="
sed -n '4296,4325p' "$F" | cat -A
echo
echo "=== confirm current return lines in both fns ==="
grep -n "GGML_STATUS_SUCCESS\|return;" "$F" | awk -F: '$1>=4296 && $1<=4325'
