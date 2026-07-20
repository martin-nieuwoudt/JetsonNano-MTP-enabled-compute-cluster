cd /home/jetson
echo "=== STABLE llama.cpp CMakeLists.txt fattn glob ==="
grep -n "fattn\|GGML_CUDA_FA\|template-instances" llama.cpp/ggml/src/ggml-cuda/CMakeLists.txt | head -30
echo ""
echo "=== STABLE: show lines around fattn glob ==="
grep -n "file(GLOB.*fattn\|GGML_CUDA_FA\b" llama.cpp/ggml/src/ggml-cuda/CMakeLists.txt
echo ""
echo "=== STABLE fattn-tile.cuh: are get_nthreads/get_occupancy constexpr? ==="
grep -n "ggml_cuda_fattn_tile_get_nthreads\|ggml_cuda_fattn_tile_get_occupancy\|constexpr" llama.cpp/ggml/src/ggml-cuda/fattn-tile.cuh | head -20
echo ""
echo "=== STABLE: does it have the cc param version? ==="
grep -n "const int cc)" llama.cpp/ggml/src/ggml-cuda/fattn-tile.cuh | head
