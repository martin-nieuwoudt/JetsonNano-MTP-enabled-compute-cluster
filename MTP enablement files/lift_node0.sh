set -e
cd /home/jetson/llama.cpp-mtp

# 1) Extract llamita reference into a temp dir
rm -rf /home/jetson/llamita_cuda
mkdir -p /home/jetson/llamita_cuda
tar -xf /home/jetson/llamita_cuda.tar -C /home/jetson/llamita_cuda

# 2) Create a reversible git branch so the working tree is never destructive
git stash -u >/dev/null 2>&1 || true
git checkout -b mtp-cuda-c14-port 2>/dev/null || git checkout mtp-cuda-c14-port
git stash pop >/dev/null 2>&1 || true

# 3) Selective lift: for every .cu/.cuh in MTP tree, if llamita has the same
#    relative file, copy it over. MTP-only files are left untouched.
SRC=/home/jetson/llamita_cuda/ggml/src/ggml-cuda
DST=/home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda
lifted=0
skipped=0
while IFS= read -r f; do
    rel="${f#$DST/}"
    if [ -f "$SRC/$rel" ]; then
        cp -f "$SRC/$rel" "$f"
        lifted=$((lifted+1))
    else
        skipped=$((skipped+1))
    fi
done < <(find "$DST" -type f \( -name '*.cu' -o -name '*.cuh' \))

echo "LIFTED=$lifted  SKIPPED(MTP-only)=$skipped"

# 4) Re-apply the MTP-specific patches that are NOT in llamita:
#    - vendors/cuda.h bf16 guard (llamita has its own; keep MTP's already-patched one)
#    - CMakeLists: ensure allreduce excluded + CMAKE_CUDA_STANDARD 14 present
echo "== CMakeLists allreduce exclude present? =="
grep -q "allreduce.cu\$" ggml/src/ggml-cuda/CMakeLists.txt && echo "  yes" || echo "  NO - need to add"
echo "== CMakeLists CMAKE_CUDA_STANDARD 14 present? =="
grep -q "CMAKE_CUDA_STANDARD 14" ggml/src/ggml-cuda/CMakeLists.txt && echo "  yes" || echo "  NO - need to add"

# 5) Count remaining C++17 features after lift
echo "== remaining if constexpr in tree =="
grep -rn "if constexpr" ggml/src/ggml-cuda/ | wc -l
echo "== remaining is_same_v in tree =="
grep -rn "is_same_v" ggml/src/ggml-cuda/ | wc -l
