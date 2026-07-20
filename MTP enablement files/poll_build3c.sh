cd /home/jetson
echo "=== nvcc command lines (output paths) ==="
for p in $(pgrep nvcc); do
  tr '\0' ' ' < /proc/$p/cmdline 2>/dev/null | grep -o '\-o [^ ]*' | head -1
done
echo ""
echo "=== broader .o search across build ==="
find /home/jetson/build -name '*.o' 2>/dev/null | wc -l
echo ""
echo "=== is make still running? ==="
pgrep -c make || echo "no make"
echo ""
echo "=== total build dir size ==="
du -sh /home/jetson/build 2>/dev/null
