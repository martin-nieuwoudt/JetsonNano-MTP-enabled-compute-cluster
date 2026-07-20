cd /home/jetson/llama.cpp-mtp
echo "=== nvcc running ==="
pgrep -c nvcc || echo 0
echo "=== .cu.o compiled count ==="
find build/ggml/src/ggml-cuda/CMakeFiles/ggml-cuda.dir -name '*.cu.o' 2>/dev/null | wc -l
echo "=== total .cu sources ==="
ls ggml/src/ggml-cuda/*.cu 2>/dev/null | wc -l
echo "=== log tail ==="
tail -5 /home/jetson/mtp_build.log
echo "=== fatal errors so far ==="
grep -i "fatal error\|Error 1\|Error 2" /home/jetson/mtp_build.log | tail -5 || echo none
