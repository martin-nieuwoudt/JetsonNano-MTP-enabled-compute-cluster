cd /home/jetson/llama.cpp-mtp
echo "=== softmax.cu.o exists? ==="
ls -la build/ggml/src/ggml-cuda/CMakeFiles/ggml-cuda.dir/softmax.cu.o 2>/dev/null || echo "NOT YET"
echo "=== mmq.cu.o exists? ==="
ls -la build/ggml/src/ggml-cuda/CMakeFiles/ggml-cuda.dir/mmq.cu.o 2>/dev/null || echo "NOT YET"
echo "=== total .cu.o ==="
find build/ggml/src/ggml-cuda/CMakeFiles/ggml-cuda.dir -name '*.cu.o' 2>/dev/null | wc -l
echo "=== nvcc running ==="
pgrep -c nvcc || echo 0
