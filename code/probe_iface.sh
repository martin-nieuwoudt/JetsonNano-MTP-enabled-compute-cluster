#!/usr/bin/env bash
KEY=/home/marti/.ssh/id_ed25519
ip="192.168.50.150"
ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "jetson@$ip" bash <<'EOF'
echo "=== interfaces with an IP on 192.168.50.x ==="
ip -o -4 addr show 2>/dev/null | awk '{print $2, $4}'
echo "=== default route iface ==="
ip route show default 2>/dev/null | awk '{print $5}'
echo "=== all non-lo links ==="
ip -o link show 2>/dev/null | awk '{print $2}' | sed 's/:$//'
EOF
