#!/usr/bin/env bash
# 1) Kill stray test servers on the PC (ports 8086/8087)
# 2) Reboot .157 to clear its wedged CUDA context
# 3) Wait for it to return, confirm RPC worker is back on 50052
set -e
echo "=== killing stray PC test servers ==="
# find llama-server.exe procs on 8086/8087 and stop them
tasklist //FI "IMAGENAME eq llama-server.exe" 2>/dev/null || true

echo "=== rebooting .157 ==="
ssh -o BatchMode=yes jetson@192.168.50.157 'sudo reboot' || true
echo "reboot issued; waiting 60s for return..."
sleep 60

echo "=== checking .157 RPC worker ==="
for attempt in 1 2 3 4 5 6; do
  if ssh -o BatchMode=yes -o ConnectTimeout=5 jetson@192.168.50.157 'pgrep -f ggml-rpc-server >/dev/null && echo UP || echo DOWN' 2>/dev/null; then
    break
  fi
  echo "  (not back yet, wait $attempt)"; sleep 15
done
