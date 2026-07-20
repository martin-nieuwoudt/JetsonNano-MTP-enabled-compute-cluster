#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'grep -n "GGML_CUDA_NO_FA\|ggml_cuda_flash_attn_ext\b\|GGML_OP_FLASH_ATTN_EXT" /home/jetson/llamita_cuda/ggml/src/ggml-cuda/ggml-cuda.cu'
