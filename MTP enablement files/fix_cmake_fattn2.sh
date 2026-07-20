cd /home/jetson/llama.cpp-mtp
F=ggml/src/ggml-cuda/CMakeLists.txt
# restore from backup
cp "${F}.bak_fattn" "$F"
# Comment out exactly lines 107-110 (fattn-tile glob, its append, fattn-mma glob, its append)
sed -i '107s|^|#|; 108s|^|#|; 109s|^|#|; 110s|^|#|' "$F"
echo "=== result lines 105-118 ==="
sed -n '105,118p' "$F"
echo ""
echo "=== verify mmq glob still active (line 111-112) ==="
sed -n '111,113p' "$F"
