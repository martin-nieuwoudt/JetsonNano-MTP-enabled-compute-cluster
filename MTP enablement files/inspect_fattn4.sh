cd /home/jetson/llama.cpp-mtp
echo "=== CMakeLists.txt lines 100-130 ==="
sed -n '100,130p' ggml/src/ggml-cuda/CMakeLists.txt
echo ""
echo "=== how is GGML_CUDA_FA set? (option/default) ==="
grep -n "GGML_CUDA_FA\|GGML_CUDA_NO_FA\|option(" ggml/src/ggml-cuda/CMakeLists.txt | head -20
echo ""
echo "=== fattn-tile.cuh: is the whole file guarded by GGML_CUDA_NO_FA? ==="
grep -n "GGML_CUDA_NO_FA\|#if\|#endif\|#ifdef" ggml/src/ggml-cuda/fattn-tile.cuh | head -30
