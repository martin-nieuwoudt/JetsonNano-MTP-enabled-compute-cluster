#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'grep -rn "ggml_cuda_flash_attn_ext\b\|ggml_cuda_flash_attn_ext_supported\|GGML_CUDA_NO_FA" /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/fattn.cu'
