cd /home/jetson/llama.cpp-mtp
echo "=== fattn.cu: GGML_CUDA_NO_FA guard? ==="
grep -n "GGML_CUDA_NO_FA\|#if\|#endif\|#ifdef" ggml/src/ggml-cuda/fattn.cu | head -20
echo ""
echo "=== fattn.cu head ==="
sed -n '1,30p' ggml/src/ggml-cuda/fattn.cu
echo ""
echo "=== does fattn.cu include fattn-tile.cuh? ==="
grep -n "fattn-tile" ggml/src/ggml-cuda/fattn.cu
echo ""
echo "=== confirm MTP CMakeLists lines 105-112 ==="
sed -n '105,112p' ggml/src/ggml-cuda/CMakeLists.txt
