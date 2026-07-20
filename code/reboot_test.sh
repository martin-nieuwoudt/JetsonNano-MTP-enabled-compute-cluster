#!/usr/bin/env bash
# Cold-boot proof: reboot node, wait for it to return, confirm RPC auto-started via systemd.
KEY=/home/marti/.ssh/id_ed25519
USER=jetson
ip="192.168.50.160"
echo "=== rebooting $ip ==="
ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$USER@$ip" "sudo reboot" 2>&1 || echo "(reboot issued)"
echo "=== waiting for node to go down ==="
for i in $(seq 1 30); do
  if ! ping -c1 -W2 "$ip" >/dev/null 2>&1; then echo "node DOWN after ${i}x2s"; break; fi
  sleep 2
done
echo "=== waiting for node to come back up ==="
for i in $(seq 1 60); do
  if ping -c1 -W2 "$ip" >/dev/null 2>&1; then echo "node UP after ~$((i*2))s"; break; fi
  sleep 2
done
sleep 5
echo "=== checking RPC auto-start (systemd) ==="
ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$USER@$ip" bash <<'EOF'
echo "enabled: $(systemctl is-enabled llama-rpc.service)"
echo "active:  $(systemctl is-active llama-rpc.service)"
ss -ltnp 2>/dev/null | grep ':50052' || echo "NOT LISTENING"
pgrep -af ggml-rpc-server | head -1
EOF
