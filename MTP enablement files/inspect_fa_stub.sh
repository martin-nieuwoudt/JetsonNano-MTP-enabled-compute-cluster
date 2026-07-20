#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'echo "=== MTP fa-stub.cu? ==="; ls -la /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/fa-stub.cu 2>&1; echo "=== STABLE fa-stub.cu content ==="; cat /home/jetson/llamita_cuda/ggml/src/ggml-cuda/fa-stub.cu; echo "=== STABLE CMakeLists fa-stub glob? ==="; grep -n "fa-stub" /home/jetson/llamita_cuda/ggml/src/ggml-cuda/CMakeLists.txt'
