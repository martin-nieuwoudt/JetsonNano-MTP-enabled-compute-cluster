cd /home/jetson/llama.cpp-mtp
F=ggml/src/ggml-cuda/CMakeLists.txt
cp "$F" "${F}.bak_nvfp4b"
# After the mmq glob append (line 111-112), add another exclude filter.
# Find the mmq append block and insert exclude right after.
sed -i '/file(GLOB   SRCS "template-instances\/mmq\*\.cu")/{n;a\    list(FILTER GGML_SOURCES_CUDA EXCLUDE REGEX "mmq-instance-nvfp4.cu$")}' "$F"
echo "=== lines 104-116 ==="
sed -n '104,116p' "$F"
