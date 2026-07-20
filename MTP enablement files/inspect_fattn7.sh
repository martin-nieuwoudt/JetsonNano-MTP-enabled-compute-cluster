cd /home/jetson/llama.cpp-mtp
echo "=== MTP fattn-tile.cuh lines 285-310 (function defs) ==="
sed -n '285,310p' ggml/src/ggml-cuda/fattn-tile.cuh
echo ""
echo "=== MTP: are the 3-arg device versions constexpr? full grep ==="
grep -n "static constexpr __device__ int ggml_cuda_fattn_tile_get_nthreads\|static __device__ int ggml_cuda_fattn_tile_get_nthreads\|static constexpr __host__ __device__ int ggml_cuda_fattn_tile_get_nthreads" ggml/src/ggml-cuda/fattn-tile.cuh
echo ""
echo "=== MTP: get_nbatch_fa / get_nbatch_K (used in constexpr at 789-791) ==="
grep -n "ggml_cuda_fattn_tile_get_nbatch_fa\|ggml_cuda_fattn_tile_get_nbatch_K" ggml/src/ggml-cuda/fattn-tile.cuh | head
