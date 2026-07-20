cd /home/jetson
echo "=== build_mtp.sh proc ==="
pgrep -af build_mtp.sh || echo "build_mtp.sh NOT running"
echo "=== make proc ==="
pgrep -af make || echo "no make"
echo "=== cc1plus/g++/nvcc ==="
pgrep -c cc1plus 2>/dev/null || echo "0 cc1plus"
pgrep -c nvcc 2>/dev/null || echo "0 nvcc"
echo "=== any .o in build (cpu) ==="
find /home/jetson/llama.cpp-mtp/build -name '*.o' 2>/dev/null | wc -l
echo "=== log tail ==="
tail -8 /home/jetson/mtp_build.log
