#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'sed -n "2700,2745p" /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/ggml-cuda.cu'
