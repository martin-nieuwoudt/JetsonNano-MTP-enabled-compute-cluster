#!/usr/bin/env bash
# Reproduce the EXACT proven Step B command: 3 nodes, -t 2, port 50053
# Restart .151/.152/.153 workers with -t 2 on 50053, then run the proven server cmd
set -e
for ip in 192.168.50.151 192.168.50.152 192.168.50.153; do
  ssh -o BatchMode=yes "jetson@$ip" 'bash -s' <<'EOF'
pkill -f "ggml-rpc-server" 2>/dev/null || true
sleep 1
cd /home/jetson/llama.cpp-mtp/build/bin
nohup ./ggml-rpc-server -H 0.0.0.0 -p 50053 -t 2 >/tmp/rpc_50053.log 2>&1 &
sleep 2
echo "$(hostname) -> $(pgrep -af 50053 | head -1 | cut -c1-60)"
EOF
done
