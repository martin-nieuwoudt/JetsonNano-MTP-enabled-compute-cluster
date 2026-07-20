cd /home/jetson
echo "=== log lines 1-45 (first error block) ==="
sed -n '1,45p' /home/jetson/mtp_build.log
echo ""
echo "=== build_mtp.sh content ==="
cat /home/jetson/build_mtp.sh
echo ""
echo "=== does fattn-tile-instance get guarded by GGML_CUDA_NO_FA? ==="
grep -rn "GGML_CUDA_NO_FA\|fattn-tile-instance" /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/CMakeLists.txt | head -30
