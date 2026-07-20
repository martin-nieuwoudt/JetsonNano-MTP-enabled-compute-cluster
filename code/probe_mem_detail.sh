#!/usr/bin/env bash
KEY=/home/marti/.ssh/id_ed25519
USER=jetson
for n in 150 160; do
  ip="192.168.50.$n"
  echo "===== $ip ====="
  ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$USER@$ip" bash <<'EOF'
echo "--- /proc/meminfo (key lines) ---"
grep -E 'MemTotal|MemFree|MemAvailable|Buffers|Cached|SwapTotal|SwapFree' /proc/meminfo
echo "--- top RSS processes ---"
ps -eo pid,comm,rss,vsz --sort=-rss | head -8
echo "--- is swap enabled? ---"
swapon --show 2>/dev/null || echo "no swap"
echo "--- OOM events since boot ---"
dmesg 2>/dev/null | grep -c 'Out of memory'
EOF
done
