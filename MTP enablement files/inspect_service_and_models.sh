#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'bash -s' <<'EOF'
echo "=== llama-rpc.service ==="
cat /etc/systemd/system/llama-rpc.service
echo "=== search for any .gguf that is NOT vocab ==="
find / -maxdepth 6 -iname "*.gguf" 2>/dev/null | grep -vi vocab
echo "=== search model_keys.txt anywhere ==="
find / -maxdepth 6 -iname "model_keys.txt" 2>/dev/null
echo "=== any large files (model shards) >100MB in /home/jetson ==="
find /home/jetson -maxdepth 5 -type f -size +100M 2>/dev/null
echo "=== MTP models dir listing ==="
ls -la /home/jetson/llama.cpp-mtp/models/ 2>/dev/null | head -50
EOF
