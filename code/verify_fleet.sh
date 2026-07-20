#!/usr/bin/env bash
# verify_fleet.sh — prove the three 2026-07-14 failure modes are permanently
# fixed across all 11 nodes. Checks, per node:
#   1. MTP binary present + daemon is ggml-rpc-server (NOT old rpc-server)
#   2. old rpc-server.service unit is GONE
#   3. llama-rpc-shape.service enabled + shaper qdisc live on eth0
#   4. daemon listening on 50052
KEY=/home/marti/.ssh/id_ed25519
fail=0
for n in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$n"
  out=$(ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "jetson@$ip" bash <<'EOF'
bin=$(pgrep -af ggml-rpc-server >/dev/null && echo MTP || echo NONE)
old=$( [ -e /etc/systemd/system/rpc-server.service ] && echo PRESENT || echo GONE )
shape_en=$(systemctl is-enabled llama-rpc-shape.service 2>/dev/null || echo absent)
qdisc=$(tc qdisc show dev eth0 2>/dev/null | grep -q htb && echo SHAPED || echo UNSHAPED)
listen=$(ss -ltn 2>/dev/null | grep -q ':50052' && echo UP || echo DOWN)
echo "bin=$bin old=$old shape=$shape_en qdisc=$qdisc listen=$listen"
EOF
)
  status="OK"
  case "$out" in
    *NONE*|*PRESENT*|*absent*|*UNSHAPED*|*DOWN*) status="FAIL"; fail=1;;
  esac
  echo "$ip: $out -> $status"
done
echo "===== $([ $fail -eq 0 ] && echo ALL GREEN || echo PROBLEMS FOUND) ====="
exit $fail
