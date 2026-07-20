cd /home/jetson/llama.cpp-mtp
F=ggml/src/ggml-cuda/CMakeLists.txt
cp "$F" "${F}.bak_fattn"
# Comment out the fattn-tile and fattn-mma template-instance globs (4 lines)
sed -i \
  -e 's|^\([[:space:]]*file(GLOB[[:space:]]*SRCS "template-instances/fattn-tile\*\.cu")\)|#\1|' \
  -e 's|^\([[:space:]]*list(APPEND GGML_SOURCES_CUDA ${SRCS})\)|#\1|' \
  -e 's|^\([[:space:]]*file(GLOB[[:space:]]*SRCS "template-instances/fattn-mma\*\.cu")\)|#\1|' \
  "$F"
echo "=== result lines 105-118 ==="
sed -n '105,118p' "$F"
