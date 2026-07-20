#!/bin/bash
# probe_node0_mtp_help.sh - dump full help of b9886 ggml-rpc-server
ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=no jetson@192.168.50.150 bash -s <<'REMOTE'
/home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server --help 2>&1
REMOTE
