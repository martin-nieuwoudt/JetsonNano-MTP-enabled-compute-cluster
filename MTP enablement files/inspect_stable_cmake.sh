#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'sed -n "100,135p" /home/jetson/llamita_cuda/ggml/src/ggml-cuda/CMakeLists.txt'
