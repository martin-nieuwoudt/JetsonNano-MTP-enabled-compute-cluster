#!/bin/bash
cd /home/jetson/llama.cpp-mtp
echo "=== GGML_STATUS_SUCCESS definition (whole tree) ==="
grep -rn "define GGML_STATUS_SUCCESS\|GGML_STATUS_SUCCESS =\|GGML_STATUS_SUCCESS," ggml/include 2>/dev/null | head
echo "=== enum ggml_status definition ==="
grep -rn "enum ggml_status" ggml/include 2>/dev/null | head
echo "=== show the enum block ==="
f=$(grep -rln "enum ggml_status {" ggml/include 2>/dev/null | head -1); echo "FILE: $f"
[ -n "$f" ] && grep -n -A12 "enum ggml_status {" "$f"
echo "=== line 901 context (function it belongs to) ==="
awk 'NR<=901 && /(static|enum ggml_status|void|bool).*\(.*\)\s*\{?$/{sig=NR": "$0} NR==901{print sig; print NR": "$0}' ggml/src/ggml-cuda/ggml-cuda.cu
sed -n "880,905p" ggml/src/ggml-cuda/ggml-cuda.cu
echo "=== mul_mat_id signature (2273) ==="
sed -n "2273,2276p" ggml/src/ggml-cuda/ggml-cuda.cu
echo "=== unregister_host_buffer full decl (4322) ==="
sed -n "4318,4325p" ggml/src/ggml-cuda/ggml-cuda.cu
