cd /home/jetson/llama.cpp-mtp
echo "=== CMakeLists.txt around line 140-175 (NO_FA guard) ==="
sed -n '140,175p' ggml/src/ggml-cuda/CMakeLists.txt
echo ""
echo "=== template-instances section in CMakeLists.txt ==="
grep -n "template-instances\|fattn\|NO_FA\|GGML_CUDA_FA" ggml/src/ggml-cuda/CMakeLists.txt
echo ""
echo "=== fattn-tile-instance-dkq112-dv112.cu head ==="
sed -n '1,15p' ggml/src/ggml-cuda/template-instances/fattn-tile-instance-dkq112-dv112.cu
echo ""
echo "=== fattn-tile.cuh line 730-745 ==="
sed -n '730,745p' ggml/src/ggml-cuda/fattn-tile.cuh
