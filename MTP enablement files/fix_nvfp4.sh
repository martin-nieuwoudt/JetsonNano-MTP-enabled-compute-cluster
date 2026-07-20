cd /home/jetson/llama.cpp-mtp
F=ggml/src/ggml-cuda/CMakeLists.txt
cp "$F" "${F}.bak_nvfp4"
# Add nvfp4 instance to the EXCLUDE filter (line 106)
sed -i '106s|$|; list(FILTER GGML_SOURCES_CUDA EXCLUDE REGEX "mmq-instance-nvfp4.cu$")|' "$F"
echo "=== line 106 now ==="
sed -n '106,107p' "$F"
echo ""
echo "=== verify mmq glob still active (line 111) ==="
sed -n '111,112p' "$F"
