cd /home/jetson/llama.cpp-mtp
echo "=== mmq-instance-nvfp4.cu content ==="
cat ggml/src/ggml-cuda/template-instances/mmq-instance-nvfp4.cu
echo ""
echo "=== how is nvfp4 type_traits defined in mmq.cuh? (search) ==="
grep -n "GGML_TYPE_NVFP4\|nvfp4\|NVFP4" ggml/src/ggml-cuda/mmq.cuh | head -20
echo ""
echo "=== is there an arch guard around nvfp4 in mmq.cuh? ==="
grep -n "GGML_CUDA_ARCH_COMPUTE\|__CUDA_ARCH__\|sm_100\|SM100\|blackwell\|BLACKWELL" ggml/src/ggml-cuda/mmq.cuh | head
echo ""
echo "=== llamita_cuda: does it have mmq-instance-nvfp4.cu? ==="
ls /home/jetson/llamita_cuda/ggml/src/ggml-cuda/template-instances/ 2>/dev/null | grep -i nvfp4 || echo "NO nvfp4 instance in llamita"
echo ""
echo "=== llamita mmq.cuh nvfp4 guard ==="
grep -n "GGML_TYPE_NVFP4\|nvfp4" /home/jetson/llamita_cuda/ggml/src/ggml-cuda/mmq.cuh 2>/dev/null | head
