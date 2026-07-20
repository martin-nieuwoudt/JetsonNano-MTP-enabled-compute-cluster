#!/usr/bin/env bash
echo "=== current llama-rpc.service on node0 ==="
ssh -o BatchMode=yes jetson@192.168.50.150 'cat /etc/systemd/system/llama-rpc.service 2>&1'
echo "=== full MTP --help ==="
ssh -o BatchMode=yes jetson@192.168.50.150 '/home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server --help 2>&1 | head -60'
