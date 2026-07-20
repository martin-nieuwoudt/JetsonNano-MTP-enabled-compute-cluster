#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'cd /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda && \
sed -i "s|    list(FILTER GGML_SOURCES_CUDA EXCLUDE REGEX \"allreduce.cu\$\")|    list(FILTER GGML_SOURCES_CUDA EXCLUDE REGEX \"allreduce.cu\$\")\n    list(FILTER GGML_SOURCES_CUDA EXCLUDE REGEX \"fattn.*\\.cu\")|" CMakeLists.txt && \
echo "=== applied ===" && sed -n "104,108p" CMakeLists.txt'
