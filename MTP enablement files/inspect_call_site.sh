#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'grep -n "ggml_cuda_flash_attn_ext\b\|GGML_CUDA_NO_FA" /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/ggml-cuda.cu'
