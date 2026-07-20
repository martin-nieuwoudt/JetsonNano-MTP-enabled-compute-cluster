#!/bin/bash
cd /home/jetson/llama.cpp-mtp
F=ggml/src/ggml-cuda/mmq.cu
echo "=== mmq.cu 295-380 (line numbers) ==="
sed -n '295,380p' "$F" | cat -n
echo
echo "=== grep for C++17-isms in mmq.cu ==="
grep -n "if constexpr\|auto \[\|auto&\|std::is_same_v\|->.*requires\|concept \|fold\|std::apply\|structured" "$F" | head -40
