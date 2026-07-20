#!/bin/bash
cd /home/jetson/llama.cpp-mtp
echo "=== common.cuh around 1037 (forward decl) ==="
sed -n "1030,1042p" ggml/src/ggml-cuda/common.cuh
echo
echo "=== how is ggml_status introduced in common.cuh? (typedef? enum? using?) ==="
grep -n "ggml_status" ggml/src/ggml-cuda/common.cuh | head
echo
echo "=== is ggml.h / ggml-backend.h included in common.cuh? ==="
grep -n "#include" ggml/src/ggml-cuda/common.cuh | head
echo
echo "=== the RAW nvcc error for line 604 (full block) ==="
grep -n -A6 "ggml-cuda.cu(604)" /home/jetson/mtp_build.log
echo
echo "=== does ggml.h define 'enum ggml_status' or 'typedef enum {...} ggml_status'? ==="
sed -n "355,365p" ggml/include/ggml.h
