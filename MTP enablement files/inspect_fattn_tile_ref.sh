#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'grep -n "flash_attn_ext_tile_case\|GGML_CUDA_NO_FA" /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/fattn.cu'
