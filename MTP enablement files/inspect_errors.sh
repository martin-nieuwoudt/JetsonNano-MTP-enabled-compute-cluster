#!/bin/bash
cd /home/jetson/llama.cpp-mtp
echo "=== ALL error: lines in build log ==="
grep -n "error:" /home/jetson/mtp_build.log
echo "=== count ==="
grep -c "error:" /home/jetson/mtp_build.log
echo "=== graph_compute declaration ==="
grep -n "ggml_backend_cuda_graph_compute" ggml/src/ggml-cuda/ggml-cuda.cu | head
echo "=== graph_optimize declaration (line 4009 context) ==="
sed -n "4009,4012p" ggml/src/ggml-cuda/ggml-cuda.cu
echo "=== unregister_host_buffer declaration (line 4322 context) ==="
sed -n "4322,4326p" ggml/src/ggml-cuda/ggml-cuda.cu
echo "=== interface field types for graph_compute / graph_optimize ==="
grep -n "graph_compute\|graph_optimize" ggml/src/ggml-backend-impl.h
