#!/usr/bin/env bash
# install_watchdog.sh - deploy the self-heal watchdog + ensure llama-rpc.service
# is enabled (boot-persistent) on all 11 nodes. Decentralised failover: every
# node monitors and restarts its OWN server; no cross-node SSH, no session dep.
KEY=/home/marti/.ssh/id_ed25519
USER=jetson
SRC_DIR=/mnt/c/Users/marti/Desktop/Cluster/code
WATCHDOG=$SRC_DIR/rpc_watchdog.sh
WATCHDOG_UNIT=$SRC_DIR/rpc_watchdog.service
RPC_UNIT=$SRC_DIR/llama-rpc.service
DEST_BIN=/home/jetson/llama.cpp-mtp/build/bin

for n in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$n"
  echo "===== $ip ====="
  scp -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no \
      "$WATCHDOG" "$WATCHDOG_UNIT" "$RPC_UNIT" "jetson@$ip:/tmp/" 2>&1
  ssh -i "$KEY" -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "$USER@$ip" bash <<EOF
set -e
sudo cp /tmp/rpc_watchdog.sh $DEST_BIN/rpc_watchdog.sh
sudo chmod 755 $DEST_BIN/rpc_watchdog.sh
sudo cp /tmp/rpc_watchdog.service /etc/systemd/system/rpc_watchdog.service
sudo chown root:root /etc/systemd/system/rpc_watchdog.service
sudo cp /tmp/llama-rpc.service /etc/systemd/system/llama-rpc.service
sudo chown root:root /etc/systemd/system/llama-rpc.service
sudo systemctl daemon-reload
sudo systemctl enable llama-rpc.service
sudo systemctl enable rpc_watchdog.service
sudo systemctl restart llama-rpc.service
sudo systemctl restart rpc_watchdog.service
sleep 2
if ss -ltnp 2>/dev/null | grep -q ':50052'; then echo "RPC UP"; else echo "RPC NOT UP"; fi
systemctl is-active --quiet rpc_watchdog.service && echo "WATCHDOG UP" || echo "WATCHDOG NOT UP"
EOF
done
echo "DONE"
