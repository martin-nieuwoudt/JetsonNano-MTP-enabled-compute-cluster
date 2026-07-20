#!/bin/bash
cd /home/jetson/llama.cpp-mtp
F=ggml/src/ggml-cuda/ggml-cuda.cu
echo "=== PROC CHECK ==="
pgrep -af build_mtp.sh | grep -v grep || echo "NO build_mtp running"
pgrep -af nvcc | grep -v grep || echo "NO nvcc running"
echo
echo "=== LOG MTIME ==="
stat -c '%y' /home/jetson/mtp_build.log
echo
echo "=== CURRENT STATE: function decl + offending return for each candidate line ==="
for L in 102 107 111 410 599 604 617 854 901 1385 1790 2273 2293 2298 2305 2310 2318 2425 2430 3925 3981 4009 4027 4034 4322; do
  # find nearest function signature above L
  sig=$(awk -v t=$L 'NR<=t && /(^static|^enum ggml_status|^void|^bool|__global__|__device__).*\([^;]*\)\s*\{?$/{s=NR": "$0} END{print s}' "$F")
  echo "--- L$L | $sig"
  sed -n "${L}p" "$F"
done
