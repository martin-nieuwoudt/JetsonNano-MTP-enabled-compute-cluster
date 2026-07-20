#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'bash -s' <<'EOF'
echo "=== model_keys.txt location ==="
find /home/jetson -maxdepth 3 -iname "model_keys.txt" 2>/dev/null
echo "=== GGUF files on node0 ==="
find /home/jetson -maxdepth 4 -iname "*.gguf" 2>/dev/null
echo "=== running servers (port check) ==="
pgrep -af "ggml-rpc-server\|llama-rpc\|50052\|50053" 2>/dev/null
echo "=== fleet service units ==="
ls -la /etc/systemd/system/ 2>/dev/null | grep -i "llama\|rpc\|mtp"
echo "=== models dir? ==="
ls -la /home/jetson/ 2>/dev/null | head -40
EOF
