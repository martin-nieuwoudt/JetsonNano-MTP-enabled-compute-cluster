#!/usr/bin/env bash
# Kill the stray 50053 workers, confirm 50052 fleet workers are up on .151/.152/.153
for ip in 192.168.50.151 192.168.50.152 192.168.50.153; do
  ssh -o BatchMode=yes "jetson@$ip" 'bash -s' <<'EOF'
pkill -f "50053" 2>/dev/null || true
sleep 1
echo "$(hostname): $(pgrep -af '50052' | head -1 | cut -c1-55)"
EOF
done
