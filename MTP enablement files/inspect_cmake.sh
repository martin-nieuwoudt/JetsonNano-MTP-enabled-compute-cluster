cd /home/jetson/llama.cpp-mtp
echo "=== MTP CMakeLists.txt git diff (fattn glob area) ==="
git diff ggml/src/ggml-cuda/CMakeLists.txt 2>/dev/null | grep -A3 -B3 "fattn-tile\|fattn-mma\|GGML_CUDA_FA\|template-instances" | head -60
echo ""
echo "=== llamita_cuda CMakeLists.txt fattn glob ==="
grep -n "fattn-tile\|fattn-mma\|GGML_CUDA_FA\|template-instances\|GGML_CUDA_NO_FA" /home/jetson/llamita_cuda/ggml/src/ggml-cuda/CMakeLists.txt | head -30
echo ""
echo "=== llamita_cuda CUDA version / does it build fattn-tile? ==="
ls /home/jetson/llamita_cuda/build/ggml/src/ggml-cuda/CMakeFiles/ggml-cuda.dir/template-instances/ 2>/dev/null | head || echo "no llamita build objs"
echo ""
echo "=== llamita_cuda: is there a build dir at all? ==="
ls -d /home/jetson/llamita_cuda/build 2>/dev/null || echo "NO llamita build dir"
