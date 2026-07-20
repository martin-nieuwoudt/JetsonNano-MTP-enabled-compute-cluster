#!/bin/bash
cd /home/jetson/llama.cpp-mtp
echo "=== A. raw error block for 604 (sed, not grep -A) ==="
sed -n '/ggml-cuda.cu(604)/,/ggml-cuda.cu(617)/p' /home/jetson/mtp_build.log | head -20
echo
echo "=== B. is enum ggml_status inside a namespace in ggml.h? ==="
grep -n "namespace" ggml/include/ggml.h | head
echo "--- context around the enum (350-365) ---"
sed -n "350,366p" ggml/include/ggml.h
echo
echo "=== C. does ggml-backend.h define its OWN enum ggml_status? ==="
grep -n "enum ggml_status\|GGML_STATUS_SUCCESS\|typedef.*ggml_status" ggml/include/ggml-backend.h | head
echo
echo "=== D. any 'int GGML_STATUS_SUCCESS' or 'const.*GGML_STATUS_SUCCESS' ? ==="
grep -rn "GGML_STATUS_SUCCESS" ggml/include/ ggml/src/ggml-cuda/ 2>/dev/null | grep -v "enum ggml_status {" | head
echo
echo "=== E. what type does ggml-backend-impl.h expect for init_tensor vs the .cu decl? ==="
echo "header line 47:"; sed -n '47p' ggml/src/ggml-backend-impl.h
echo "cu line 599:"; sed -n '599p' ggml/src/ggml-cuda/ggml-cuda.cu
