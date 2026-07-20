#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'bash -s' <<'EOF'
echo "=== coordinator binaries in MTP build/bin ==="
ls -la /home/jetson/llama.cpp-mtp/build/bin/ 2>/dev/null
echo "=== any qwen35 / qwythos / 9B gguf anywhere ==="
find / -maxdepth 7 -iname "*qwythos*" -o -iname "*9b*mtp*" -o -iname "*mythos*" 2>/dev/null | head
echo "=== rpc client/server in stable build ==="
ls /home/jetson/llama.cpp/build/bin/ 2>/dev/null | grep -i "rpc\|main\|llama-cli\|server"
EOF
