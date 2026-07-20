cd /home/jetson/llama.cpp-mtp
echo "=== where is fattn-vec globbed in MTP CMakeLists? ==="
grep -n "fattn-vec\|fattn-wmma\|fattn-mma\|fattn-tile" ggml/src/ggml-cuda/CMakeLists.txt
echo ""
echo "=== fattn-vec.cuh line 1-30 ==="
sed -n '1,30p' ggml/src/ggml-cuda/fattn-vec.cuh
echo ""
echo "=== llamita fattn-vec glob (line 116) ==="
sed -n '114,118p' /home/jetson/llamita_cuda/ggml/src/ggml-cuda/CMakeLists.txt
