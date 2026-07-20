cd /home/jetson/llama.cpp-mtp
echo "=== MTP: ggml_cuda_fattn_tile_get_config (3-arg) definition ==="
grep -n "ggml_cuda_fattn_tile_get_config\b\|static.*ggml_cuda_fattn_tile_get_config(" ggml/src/ggml-cuda/fattn-tile.cuh
echo ""
echo "=== show the get_config function(s) ==="
sed -n '255,290p' ggml/src/ggml-cuda/fattn-tile.cuh
echo ""
echo "=== STABLE llamita_cuda: are these constexpr? ==="
grep -n "static constexpr __device__ int ggml_cuda_fattn_tile_get_nthreads\|static __device__ int ggml_cuda_fattn_tile_get_nthreads\|ggml_cuda_fattn_tile_get_config" /home/jetson/llamita_cuda/ggml/src/ggml-cuda/fattn-tile.cuh | head
