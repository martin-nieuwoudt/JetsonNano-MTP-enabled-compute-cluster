#!/bin/bash
# clone_b9886.sh - shallow-clone llama.cpp tag b9886 onto node0
set -e
ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=no jetson@192.168.50.150 '
set -e
echo "=== disk before ==="; df -h /home/jetson | tail -1
if [ -d /home/jetson/llama.cpp-mtp ]; then echo "EXISTS: removing"; rm -rf /home/jetson/llama.cpp-mtp; fi
cd /home/jetson
git clone --depth 1 --branch b9886 https://github.com/ggml-org/llama.cpp.git llama.cpp-mtp 2>&1 | tail -5
cd /home/jetson/llama.cpp-mtp
echo "=== checked out ==="; git describe --tags 2>/dev/null; git log -1 --format="%H %ci"
echo "=== disk after ==="; df -h /home/jetson | tail -1
'
