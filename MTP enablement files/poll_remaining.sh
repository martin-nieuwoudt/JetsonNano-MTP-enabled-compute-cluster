cd /home/jetson/llama.cpp-mtp
echo "=== remaining .cu not yet compiled ==="
for f in ggml/src/ggml-cuda/*.cu; do
  base=$(basename "$f" .cu)
  if [ ! -f "build/ggml/src/ggml-cuda/CMakeFiles/ggml-cuda.dir/${base}.cu.o" ]; then
    echo "MISSING: $base"
  fi
done
echo "=== nvcc procs ==="
pgrep -af nvcc | head
echo "=== fatal errors ==="
grep -i "fatal error\|Error 1\|Error 2" /home/jetson/mtp_build.log | tail -5 || echo none
echo "=== log tail ==="
tail -3 /home/jetson/mtp_build.log
