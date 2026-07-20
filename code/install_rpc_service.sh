#!/usr/bin/env bash
# install_rpc_service.sh — deploy the MTP RPC daemon + anti-incast shaper to all
# 11 nodes and make BOTH boot-persistent. Hardened (Phase 12) so the three
# 2026-07-14 failure modes can NEVER recur:
#   1. WRONG BINARY ON BOOT  -> we DELETE any old rpc-server.service unit and
#      assert the MTP ggml-rpc-server binary exists before enabling.
#   2. OOM ON MARGINAL NODE  -> handled client-side by cluster_infer.py's guard
#      (model-size check); nothing to do here, but we refuse to proceed if the
#      MTP binary is missing (a missing binary would fall back to old behaviour).
#   3. CONNECTION STORM       -> deploy the tc egress shaper (apply_rpc_shaper.sh)
#      as llama-rpc-shape.service, ordered BEFORE llama-rpc.service so it is
#      always present before the daemon binds the port.
KEY=/home/marti/.ssh/id_ed25519
USER=jetson
SRC_DIR=/mnt/c/Users/marti/Desktop/Cluster/code
RPC_UNIT=$SRC_DIR/llama-rpc.service
SHAPE_UNIT=$SRC_DIR/llama-rpc-shape.service
SHAPER=$SRC_DIR/apply_rpc_shaper.sh
MTP_BIN=/home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server

for n in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$n"
  echo "===== $ip ====="
  scp -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no \
      "$RPC_UNIT" "$SHAPE_UNIT" "$SHAPER" "jetson@$ip:/tmp/" 2>&1
  ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$USER@$ip" bash <<EOF
set -e
# --- GUARD 1: MTP binary must exist (no fallback to old behaviour) ---
if [ ! -x "$MTP_BIN" ]; then echo "FATAL: MTP binary missing at $MTP_BIN"; exit 1; fi

# --- GUARD 2: delete any OLD stable unit so it can never boot ---
if [ -e /etc/systemd/system/rpc-server.service ]; then
  sudo systemctl disable --now rpc-server.service 2>/dev/null || true
  sudo rm -f /etc/systemd/system/rpc-server.service
  echo "removed old rpc-server.service"
fi

# --- deploy MTP daemon unit ---
sudo cp /tmp/llama-rpc.service /etc/systemd/system/llama-rpc.service
sudo chown root:root /etc/systemd/system/llama-rpc.service

# --- deploy shaper unit + script (root-owned, on the MTP bin dir) ---
sudo cp /tmp/llama-rpc-shape.service /etc/systemd/system/llama-rpc-shape.service
sudo chown root:root /etc/systemd/system/llama-rpc-shape.service
sudo cp /tmp/apply_rpc_shaper.sh /home/jetson/llama.cpp-mtp/build/bin/apply_rpc_shaper.sh
sudo chmod 755 /home/jetson/llama.cpp-mtp/build/bin/apply_rpc_shaper.sh

sudo systemctl daemon-reload
sudo systemctl enable llama-rpc-shape.service
sudo systemctl enable llama-rpc.service
sudo systemctl restart llama-rpc-shape.service
sudo systemctl restart llama-rpc.service
sleep 2
if ss -ltnp 2>/dev/null | grep -q ':50052'; then echo "RPC UP (MTP)"; else echo "RPC NOT UP"; fi
pgrep -af ggml-rpc-server | head -1
echo "shaper qdisc:"; tc qdisc show dev eth0 2>/dev/null | head -2
EOF
done
echo "DONE"
