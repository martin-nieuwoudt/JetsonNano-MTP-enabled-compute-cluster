cd /home/jetson
echo "=== build_mtp.sh content ==="
cat /home/jetson/build_mtp.sh
echo ""
echo "=== when was build dir created? ==="
stat -c '%y' /home/jetson/llama.cpp-mtp/build 2>/dev/null
echo ""
echo "=== does current build.make (fresh) still have nvfp4? ==="
grep -c "mmq-instance-nvfp4" /home/jetson/llama.cpp-mtp/build/ggml/src/ggml-cuda/CMakeFiles/ggml-cuda.dir/build.make 2>/dev/null
