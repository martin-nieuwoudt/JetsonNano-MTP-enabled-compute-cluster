cd /home/jetson/llama.cpp-mtp
F=ggml/src/ggml-cuda/CMakeLists.txt
cp "$F" "${F}.bak_fattnvec"
# Comment out line 118 (fattn-vec glob)
sed -i '118s|^|#|' "$F"
echo "=== lines 114-128 ==="
sed -n '114,128p' "$F"
