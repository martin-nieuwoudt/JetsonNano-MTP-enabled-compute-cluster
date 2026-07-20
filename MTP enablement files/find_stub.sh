cd /home/jetson/llama.cpp-mtp
echo "=== git ls-files stubs ==="
git ls-files | grep -i stubs
echo "=== git ls-files softmax ==="
git ls-files | grep -i softmax
echo "=== is softmax.cu modified? ==="
git status --short ggml/src/ggml-cuda/softmax.cu
echo "=== look for STABLE reference on disk ==="
ls -d /home/jetson/llama.cpp* 2>/dev/null
echo "=== search whole disk for reduce.h stub ==="
find /home/jetson -name reduce.h -path '*cooperative_groups*' 2>/dev/null
find /home/jetson -name 'reduce.h' -path '*stubs*' 2>/dev/null
