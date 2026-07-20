#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'sed -n "1200,1260p" /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/fattn-tile.cuh'
