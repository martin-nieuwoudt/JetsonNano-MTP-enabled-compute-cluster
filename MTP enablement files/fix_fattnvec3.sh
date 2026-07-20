cd /home/jetson/llama.cpp-mtp
F=ggml/src/ggml-cuda/CMakeLists.txt
# restore from backup
cp "${F}.bak_fattnvec" "$F"
# Comment out the entire fattn-vec if/else/endif block (lines 117-128)
sed -i '117s|^|#|; 118s|^|#|; 119s|^|#|; 120s|^|#|; 121s|^|#|; 122s|^|#|; 123s|^|#|; 124s|^|#|; 125s|^|#|; 126s|^|#|; 127s|^|#|; 128s|^|#|' "$F"
echo "=== lines 114-132 ==="
sed -n '114,132p' "$F"
