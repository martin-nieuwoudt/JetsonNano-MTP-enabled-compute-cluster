cd /home/jetson
echo "=== ggml-cuda.dir contents ==="
ls /home/jetson/build/ggml/src/ggml-cuda/CMakeFiles/ggml-cuda.dir/ 2>/dev/null | head
echo ""
echo "=== any .o files anywhere in build (count) ==="
find /home/jetson/build -name '*.o' 2>/dev/null | wc -l
echo ""
echo "=== any nvcc temp files ==="
find /home/jetson/build -name '*.cu*.o' 2>/dev/null | head
echo ""
echo "=== tail of full log (last 15) ==="
tail -15 /home/jetson/mtp_build.log
