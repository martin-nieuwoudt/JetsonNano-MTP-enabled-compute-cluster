#!/bin/bash
cd /home/jetson/llama.cpp-mtp
echo "=== 1. header decl of ggml_cuda_set_device (the puzzling one) ==="
grep -rn "ggml_cuda_set_device" ggml/src/ggml-cuda/*.h ggml/include/*.h 2>/dev/null
echo
echo "=== 2. ALL definitions of GGML_STATUS_SUCCESS across tree (macro? enum? int?) ==="
grep -rn "GGML_STATUS_SUCCESS" ggml/include/ggml.h | head
echo "--- any #define of it anywhere? ---"
grep -rn "define GGML_STATUS_SUCCESS" . 2>/dev/null | head
echo
echo "=== 3. Is ggml.h included in ggml-cuda.cu before line 102? ==="
grep -n "#include" ggml/src/ggml-cuda/ggml-cuda.cu | head -20
echo
echo "=== 4. Does ggml-backend-impl.h or ggml.h get pulled in? check include of ggml-backend-impl ==="
grep -rn "ggml-backend-impl.h" ggml/src/ggml-cuda/ggml-cuda.cu
echo
echo "=== 5. Full error context for 604 (init_tensor, enum-declared, errors) ==="
sed -n "599,605p" ggml/src/ggml-cuda/ggml-cuda.cu
echo "--- is there a PRIOR declaration of ggml_backend_cuda_buffer_init_tensor as void? ---"
grep -rn "ggml_backend_cuda_buffer_init_tensor" ggml/src/ggml-cuda/*.h 2>/dev/null
