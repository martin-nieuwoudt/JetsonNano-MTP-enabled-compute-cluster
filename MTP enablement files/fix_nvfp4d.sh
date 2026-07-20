cd /home/jetson/llama.cpp-mtp
F=ggml/src/ggml-cuda/CMakeLists.txt
# restore from last good backup (has the line-107 exclude)
cp "${F}.bak_nvfp4" "$F"
# Insert exclude after line 112 (mmq append)
sed -i '112a\    list(FILTER GGML_SOURCES_CUDA EXCLUDE REGEX "mmq-instance-nvfp4.cu$")' "$F"
echo "=== lines 104-116 ==="
sed -n '104,116p' "$F"
