#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'cp /home/jetson/llamita_cuda/ggml/src/ggml-cuda/fa-stub.cu /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/fa-stub.cu && echo "copied" && ls -la /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/fa-stub.cu'
