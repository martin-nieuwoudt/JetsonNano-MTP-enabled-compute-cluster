cd /home/jetson/llama.cpp-mtp
echo "=== mmq.cuh around 3340-3360 (nvfp4 block) ==="
sed -n '3340,3360p' ggml/src/ggml-cuda/mmq.cuh
echo ""
echo "=== where is GGML_TYPE_NVFP4 type_traits declared? ==="
grep -rn "GGML_TYPE_NVFP4" ggml/src/ggml-cuda/*.cuh ggml/src/ggml-cuda/*.cu 2>/dev/null | head
echo ""
echo "=== grep nvfp4 across whole ggml-cuda ==="
grep -rln "nvfp4\|NVFP4" ggml/src/ggml-cuda/ 2>/dev/null
echo ""
echo "=== CMakeLists mmq glob lines ==="
grep -n "mmq\*.cu\|list(FILTER\|allreduce" ggml/src/ggml-cuda/CMakeLists.txt
