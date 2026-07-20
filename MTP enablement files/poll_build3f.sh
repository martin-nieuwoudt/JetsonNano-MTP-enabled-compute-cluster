cd /home/jetson
echo "=== nvcc CPU time / state ==="
ps -o pid,stat,time,pcpu,comm -p $(pgrep nvcc | tr '\n' ',' | sed 's/,$//') 2>/dev/null
echo ""
echo "=== what each nvcc is compiling (source arg) ==="
for p in $(pgrep nvcc); do
  tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -o '[^ ]*\.cu' | grep -v '\-o' | head -1
done
echo ""
echo "=== any .cu.o.tmp or partial ==="
find /home/jetson/llama.cpp-mtp/build/ggml/src/ggml-cuda -name '*.o*' 2>/dev/null | head
echo ""
echo "=== free memory (OOM risk) ==="
free -m | head -2
