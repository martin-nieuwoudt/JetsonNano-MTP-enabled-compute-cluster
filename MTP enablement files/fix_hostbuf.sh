#!/bin/bash
cd /home/jetson/llama.cpp-mtp
F=ggml/src/ggml-cuda/ggml-cuda.cu
cp "$F" "$F.bak_$(date +%s)"
# 4300: bool fn early return -> return true;
# 4311: bool fn #if branch -> return true;  (inactive on CUDA10.2 but fix for correctness)
# 4317: bool fn #else branch (ACTIVE on CUDA10.2) -> return true;
# 4323: void fn -> return;
sed -i '4300s/return;/return true;/' "$F"
sed -i '4311s/return GGML_STATUS_SUCCESS;/return true;/' "$F"
sed -i '4317s/return GGML_STATUS_SUCCESS;/return true;/' "$F"
sed -i '4323s/return GGML_STATUS_SUCCESS;/return;/' "$F"
echo "=== verify ==="
sed -n '4298,4325p' "$F"
echo "=== any remaining GGML_STATUS_SUCCESS in void/bool fns? ==="
grep -n "GGML_STATUS_SUCCESS" "$F" | awk -F: '$1>=4298 && $1<=4325'
