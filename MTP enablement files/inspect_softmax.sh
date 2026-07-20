cd /home/jetson/llama.cpp-mtp
echo "=== softmax.cu head ==="
sed -n '1,40p' ggml/src/ggml-cuda/softmax.cu
echo "=== git status ==="
git status --short 2>/dev/null | head -40
echo "=== git log ==="
git log --oneline -5 2>/dev/null
echo "=== search cooperative_groups includes across cuda ==="
grep -rn "cooperative_groups" ggml/src/ggml-cuda/*.cu ggml/src/ggml-cuda/*.cuh 2>/dev/null | head -40
