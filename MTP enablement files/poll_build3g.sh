cd /home/jetson
OBJDIR=/home/jetson/llama.cpp-mtp/build/ggml/src/ggml-cuda/CMakeFiles/ggml-cuda.dir
echo "=== .cu.o count ==="
find "$OBJDIR" -name '*.cu.o' 2>/dev/null | wc -l
echo ""
echo "=== fattn-tile*.o present? ==="
find "$OBJDIR" -name 'fattn-tile*.o' 2>/dev/null
echo ""
echo "=== mmq.cu.o size ==="
ls -la "$OBJDIR/mmq.cu.o" 2>/dev/null
echo ""
echo "=== nvcc running? ==="
pgrep -c nvcc || echo 0
echo ""
echo "=== binary? ==="
ls -la /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server 2>/dev/null || echo "not yet"
echo ""
echo "=== EXIT? ==="
grep -E "EXIT=" /home/jetson/mtp_build.log || echo "still running"
