cd /home/jetson
echo "=== STABLE llama.cpp stub? ==="
ls -la llama.cpp/ggml/src/ggml-cuda/stubs/cooperative_groups/reduce.h 2>/dev/null || echo "NO stub in STABLE llama.cpp"
echo "=== llamita_cuda stub content ==="
cat llamita_cuda/ggml/src/ggml-cuda/stubs/cooperative_groups/reduce.h
echo "=== STABLE llama.cpp softmax.cu cooperative_groups lines ==="
grep -n "cooperative_groups\|reduce.h" llama.cpp/ggml/src/ggml-cuda/softmax.cu 2>/dev/null || echo "no match in STABLE"
echo "=== MTP softmax.cu diff vs HEAD ==="
cd llama.cpp-mtp && git diff ggml/src/ggml-cuda/softmax.cu 2>/dev/null | head -60
