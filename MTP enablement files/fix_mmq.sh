#!/bin/bash
cd /home/jetson/llama.cpp-mtp
F=ggml/src/ggml-cuda/mmq.cu
echo "=== cat -A 300-308 ==="
sed -n '300,308p' "$F" | cat -A
echo "=== delete stray lines 304-305 (the orphan return false; + }) ==="
cp "$F" "$F.bak_mmq_$(date +%s)"
sed -i '304,305d' "$F"
echo "=== verify 298-312 after delete ==="
sed -n '298,312p' "$F" | cat -A
