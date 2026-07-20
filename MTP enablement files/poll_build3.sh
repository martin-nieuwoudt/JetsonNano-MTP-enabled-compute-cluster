cd /home/jetson
LOG=/home/jetson/mtp_build.log
OBJDIR=/home/jetson/build/ggml/src/ggml-cuda/CMakeFiles/ggml-cuda.dir
echo "=== tail of log ==="
tail -6 "$LOG"
echo ""
echo "=== nvcc processes running ==="
pgrep -c nvcc || echo 0
echo ""
echo "=== .cu.o count (of 65) ==="
find "$OBJDIR" -name '*.cu.o' 2>/dev/null | wc -l
echo ""
echo "=== fattn-tile obj present? (should be 0 now) ==="
find "$OBJDIR" -name 'fattn-tile*.o' 2>/dev/null | wc -l
echo ""
echo "=== binary present? ==="
ls -la /home/jetson/build/bin/ggml-rpc-server 2>/dev/null || echo "not yet"
echo ""
echo "=== EXIT marker ==="
grep -E "EXIT=" "$LOG" || echo "still running"
