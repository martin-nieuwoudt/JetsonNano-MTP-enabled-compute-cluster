#!/bin/bash
cd /home/jetson/llama.cpp-mtp
F=ggml/src/ggml-cuda/ggml-cuda.cu
echo "=== mul_mat_id body: all return + control-flow lines (2273-2430) ==="
awk 'NR>=2273 && NR<=2430 && (/return/||/if \(|else|switch|case|default|for \(|while \(|do \{/){print NR": "$0}' "$F"
echo
echo "=== last 12 lines of mul_mat_id (2419-2430) ==="
sed -n '2419,2430p' "$F"
echo
echo "=== does mul_mat_id end with a return? check 2425-2430 ==="
sed -n '2425,2430p' "$F"
