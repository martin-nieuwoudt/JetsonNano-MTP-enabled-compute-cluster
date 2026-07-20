#!/bin/bash
cd /home/jetson/llama.cpp-mtp
F=ggml/src/ggml-cuda/ggml-cuda.cu
echo "=== 6 error sites: 3 lines context each ==="
for L in 410 1385 1790 4027 4034 4322; do
  echo "########## L$L ##########"
  sed -n "$((L-3)),$((L+1))p" "$F"
done
echo
echo "=== mul_mat_id (2273) full return scan + final line 2430 ==="
awk 'NR>=2273 && NR<=2430 && /return/{print NR": "$0}' "$F"
echo "--- line 2425-2432 ---"
sed -n '2425,2432p' "$F"
echo
echo "=== confirm NO other 'return GGML_STATUS_SUCCESS' inside a void/__global__ fn (sanity) ==="
grep -n "return GGML_STATUS_SUCCESS" "$F" | wc -l
