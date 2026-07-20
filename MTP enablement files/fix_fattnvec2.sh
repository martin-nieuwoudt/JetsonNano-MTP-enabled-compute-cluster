cd /home/jetson/llama.cpp-mtp
F=ggml/src/ggml-cuda/CMakeLists.txt
# Comment out the else() block that appends fattn-vec instances (lines 122-127)
sed -i '122s|^|#|; 123s|^|#|; 124s|^|#|; 125s|^|#|; 126s|^|#|; 127s|^|#|' "$F"
echo "=== lines 114-130 ==="
sed -n '114,130p' "$F"
