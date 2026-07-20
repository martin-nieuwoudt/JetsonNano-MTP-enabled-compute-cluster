#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'sed -n "1,60p" /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/fattn-tile.cu'
