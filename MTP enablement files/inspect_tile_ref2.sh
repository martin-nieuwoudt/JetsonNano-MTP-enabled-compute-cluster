#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'grep -rn "flash_attn_ext_tile_case" /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/ | grep -v "template-instances"'
