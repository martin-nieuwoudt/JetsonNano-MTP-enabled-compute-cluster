cd /home/jetson
echo "=== .cu.o count in correct dir ==="
find /home/jetson/build/ggml/src/ggml-cuda -name '*.cu.o' 2>/dev/null | wc -l
echo ""
echo "=== nvcc still running? ==="
pgrep -c nvcc || echo 0
echo ""
echo "=== binary present? ==="
ls -la /home/jetson/build/bin/ggml-rpc-server 2>/dev/null || echo "not yet"
echo ""
echo "=== EXIT marker ==="
grep -E "EXIT=" /home/jetson/mtp_build.log || echo "still running"
