#!/usr/bin/env bash
# Kill stale PC server, restart all 11 node workers fresh, confirm all UP
echo "=== killing stale PC llama-server procs ==="
taskkill //F //IM llama-server.exe 2>/dev/null || true

echo "=== restarting all 11 node workers ==="
for i in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$i"
  ssh -o BatchMode=yes "jetson@$ip" 'sudo systemctl restart llama-rpc.service' 2>/dev/null && echo "$ip restarted" || echo "$ip FAILED"
done

echo "=== waiting 10s for workers to settle ==="
sleep 10

echo "=== confirming all UP ==="
for i in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$i"
  st=$(ssh -o BatchMode=yes -o ConnectTimeout=5 "jetson@$ip" 'pgrep -f ggml-rpc-server >/dev/null && echo UP || echo DOWN' 2>/dev/null || echo UNREACH)
  echo "$ip -> $st"
done
