cd /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda
echo "===== Search for all vtables in ggml-cuda.cu ====="
grep -n "static const.*_interface\|static const.*_vtable" ggml-cuda.cu
echo ""
echo "===== Check line 4258 area more carefully ====="
sed -n '4250,4270p' ggml-cuda.cu
echo ""
echo "===== Check if there's a second backend interface ====="
grep -n "ggml_backend_i\|ggml_backend_cuda_interface" ggml-cuda.cu
