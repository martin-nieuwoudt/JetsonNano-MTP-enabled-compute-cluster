cd /home/jetson
echo "=== nvcc cwd ==="
for p in $(pgrep nvcc); do echo "pid $p cwd: $(readlink /proc/$p/cwd)"; done
echo ""
echo "=== search whole build for any .cu.o ==="
find /home/jetson/build -name '*.cu.o' 2>/dev/null
echo ""
echo "=== search for mmvf.cu.o anywhere ==="
find /home/jetson/build -name 'mmvf*' 2>/dev/null
echo ""
echo "=== build dir tree depth 3 ==="
find /home/jetson/build/ggml/src/ggml-cuda -maxdepth 2 -type d 2>/dev/null | head
