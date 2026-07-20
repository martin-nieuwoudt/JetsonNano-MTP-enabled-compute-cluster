#!/bin/bash
cd /home/jetson/llama.cpp-mtp
echo "=== grep GGML_STATUS_SUCCESS in ggml-cuda.h and all .cuh pulled in ==="
grep -rn "GGML_STATUS_SUCCESS" ggml/src/ggml-cuda/ggml-cuda.h ggml/src/ggml-cuda/*.cuh 2>/dev/null | head
echo
echo "=== grep 'define GGML_STATUS' anywhere in ggml-cuda dir ==="
grep -rn "define GGML_STATUS" ggml/src/ggml-cuda/ 2>/dev/null | head
echo
echo "=== is there a SECOND enum ggml_status (e.g. in ggml-cuda.h) ? ==="
grep -rn "enum ggml_status" ggml/src/ggml-cuda/ 2>/dev/null | head
echo
echo "=== what does ggml-cuda.h include / define around status? ==="
grep -n "status\|STATUS\|ggml_status" ggml/src/ggml-cuda/ggml-cuda.h | head -20
echo
echo "=== exact error text for 604 from the .ii preprocessed? grab raw nvcc error block ==="
grep -n -B2 -A2 "ggml-cuda.cu(604)" /home/jetson/mtp_build.log
echo
echo "=== check ggml-impl.h for status enum or macro ==="
grep -rn "GGML_STATUS_SUCCESS\|enum ggml_status" ggml/src/ggml-impl.h 2>/dev/null | head
