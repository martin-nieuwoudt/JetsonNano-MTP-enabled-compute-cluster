cd /home/jetson/llama.cpp-mtp
echo "=== git diff fattn-tile.cuh (MTP vs HEAD) ==="
git diff ggml/src/ggml-cuda/fattn-tile.cuh 2>/dev/null | head -80
echo ""
echo "=== is fattn-tile.cuh modified? ==="
git status --short ggml/src/ggml-cuda/fattn-tile.cuh
echo ""
echo "=== STABLE llamita_cuda fattn-tile.cuh line 739 area ==="
sed -n '725,745p' /home/jetson/llamita_cuda/ggml/src/ggml-cuda/fattn-tile.cuh 2>/dev/null || echo "NO STABLE fattn-tile.cuh"
echo ""
echo "=== does STABLE llamita_cuda compile fattn-tile? check its build ==="
ls -la /home/jetson/llamita_cuda/build/ggml/src/ggml-cuda/CMakeFiles/ggml-cuda.dir/template-instances/fattn-tile-instance-dkq112-dv112.cu.o 2>/dev/null || echo "no STABLE obj"
