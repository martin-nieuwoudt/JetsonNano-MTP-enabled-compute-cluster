#!/usr/bin/env bash
KEY=/home/marti/.ssh/id_ed25519
for n in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$n"
  out=$(ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "jetson@$ip" bash <<'EOF'
u=$(systemctl is-enabled llama-rpc.service 2>/dev/null)
old=$(ls /etc/systemd/system/ 2>/dev/null | grep -c rpc-server.service)
bin=$(pgrep -af ggml-rpc-server | head -1 | grep -o ggml-rpc-server)
tc=$(which tc 2>/dev/null || echo NO_TC)
ifc=$(ip -o link show 2>/dev/null | awk '{print $2}' | grep -v lo | head -1)
echo "en=$u old=$old bin=$bin tc=$tc ifc=$ifc"
EOF
)
  echo "$ip: $out"
done
