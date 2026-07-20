set -e
SRC=/home/jetson/llamita_cuda/ggml/src/ggml-cuda/stubs/cooperative_groups/reduce.h
DST=/home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/stubs/cooperative_groups/reduce.h
mkdir -p "$(dirname "$DST")"
cp "$SRC" "$DST"
echo "=== copied. content ==="
cat "$DST"
echo "=== verify path ==="
ls -la "$DST"
