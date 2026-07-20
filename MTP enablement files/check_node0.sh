#!/usr/bin/env bash
set -e
echo "=== MTP binary ==="
ssh -o BatchMode=yes jetson@192.168.50.150 'ls -la /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server 2>&1'
echo "=== --help flags ==="
ssh -o BatchMode=yes jetson@192.168.50.150 '/home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server --help 2>&1 | grep -E "(-m MEM|-p PORT|-H HOST)"'
echo "=== running rpc services ==="
ssh -o BatchMode=yes jetson@192.168.50.150 'systemctl list-units --type=service 2>/dev/null | grep -i rpc || echo "no systemd rpc units"'
echo "=== listening ports 5005x ==="
ssh -o BatchMode=yes jetson@192.168.50.150 'ss -ltnp 2>/dev/null | grep -E "5005[0-9]" || echo "none"'
echo "=== stable build still present? ==="
ssh -o BatchMode=yes jetson@192.168.50.150 'ls -la /home/jetson/llama.cpp/build/bin/rpc-server 2>&1'
