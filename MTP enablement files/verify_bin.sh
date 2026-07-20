#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'ls -la /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server && /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server --help 2>&1 | head -20'
