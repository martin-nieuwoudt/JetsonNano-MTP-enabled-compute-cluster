#!/bin/bash
cd /home/jetson/llama.cpp-mtp
H=ggml/src/ggml-backend-impl.h
echo "=== ggml_status enum def ==="
grep -n "enum ggml_status\|GGML_STATUS_SUCCESS\|GGML_STATUS_" "$H" | head -20
echo
echo "=== buffer_i struct (init_tensor / cpy_tensor / free / memset) ==="
sed -n "40,110p" "$H"
echo
echo "=== backend_i struct (graph_compute / graph_optimize / set_tensor / get_tensor) ==="
sed -n "105,145p" "$H"
