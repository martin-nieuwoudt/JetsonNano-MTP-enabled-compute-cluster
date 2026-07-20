cd /home/jetson/llama.cpp-mtp
echo "=== MTP: get_nthreads / get_occupancy definitions ==="
grep -n "ggml_cuda_fattn_tile_get_nthreads\|ggml_cuda_fattn_tile_get_occupancy\|constexpr\|__host__ __device__" ggml/src/ggml-cuda/fattn-tile.cuh | head -40
echo ""
echo "=== MTP: show the function bodies ==="
grep -n "ggml_cuda_fattn_tile_get_nthreads\|ggml_cuda_fattn_tile_get_occupancy" ggml/src/ggml-cuda/fattn-tile.cuh
