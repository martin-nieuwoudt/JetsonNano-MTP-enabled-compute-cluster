cd /home/jetson/llama.cpp-mtp
echo "=== current CMakeLists lines 104-112 ==="
sed -n '104,112p' ggml/src/ggml-cuda/CMakeLists.txt
echo ""
echo "=== is mmq-instance-nvfp4.cu still in source tree? ==="
ls -la ggml/src/ggml-cuda/template-instances/mmq-instance-nvfp4.cu
echo ""
echo "=== does build.make reference it? (from last build) ==="
grep -n "mmq-instance-nvfp4" /home/jetson/llama.cpp-mtp/build/ggml/src/ggml-cuda/CMakeFiles/ggml-cuda.dir/build.make 2>/dev/null | head
echo ""
echo "=== git diff of CMakeLists (confirm our edits are saved) ==="
git diff ggml/src/ggml-cuda/CMakeLists.txt | grep -A2 -B2 "nvfp4\|allreduce"
