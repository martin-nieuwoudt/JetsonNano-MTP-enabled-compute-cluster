#!/usr/bin/env bash
# Find which node's ggml-rpc-server recently restarted (low uptime) and check dmesg for OOM.
KEY=/home/marti/.ssh/id_ed25519
USER=jetson
for n in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$n"
  ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$USER@$ip" bash <<EOF
echo "=== $ip ==="
pid=\$(pgrep -f ggml-rpc-server | head -1)
if [ -n "\$pid" ]; then
  etime=\$(ps -o etimes= -p \$pid | tr -d ' ')
  echo "rpc pid \$pid uptime \${etime}s"
fi
echo "--- OOM in dmesg (last boot) ---"
dmesg 2>/dev/null | grep -i 'out of memory\|killed process\|oom' | tail -3 || echo "no dmesg access"
echo "--- mem available ---"
free -m | head -2
EOF
done
