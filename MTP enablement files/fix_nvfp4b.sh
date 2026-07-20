cd /home/jetson/llama.cpp-mtp
F=ggml/src/ggml-cuda/CMakeLists.txt
# restore from backup
cp "${F}.bak_nvfp4" "$F"
# Line 106: original allreduce exclude. Insert a NEW line 107 with nvfp4 exclude.
sed -i '106a\    list(FILTER GGML_SOURCES_CUDA EXCLUDE REGEX "mmq-instance-nvfp4.cu$")' "$F"
echo "=== lines 104-112 ==="
sed -n '104,112p' "$F"
