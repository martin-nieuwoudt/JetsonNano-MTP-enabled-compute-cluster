#!/usr/bin/env bash
# Kill manual orphan rpc processes so systemd owns the port cleanly.
KEY=/home/marti/.ssh/id_ed25519
USER=jetson
for n in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$n"
  echo "===== $ip ====="
  ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$USER@$ip" bash <<'EOF'
# kill any rpc-server not started by systemd (manual setsid orphans)
pkill -f 'ggml-rpc-server' 2>/dev/null
sleep 2
sudo systemctl restart llama-rpc.service
sleep 2
echo "active: $(systemctl is-active llama-rpc.service)"
ss -ltnp 2>/dev/null | grep ':50052' || echo "NOT LISTENING"
EOF
done
echo "DONE"
