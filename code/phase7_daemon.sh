#!/bin/bash
# Phase 7: Daemon Configuration (Template Node)
# From: Nano Work Plan.md — Phase 7: Daemon Configuration (Template Node)
# Run on the template Jetson Nano via SSH

set -e

echo "[PHASE 7] Configuring rpc-server daemon..."

# Create RPC Service
sudo tee /etc/systemd/system/llama-rpc.service > /dev/null << 'EOF'
[Unit]
Description=Llama.cpp RPC Slave Server Engine
After=network.target cluster-init.service
Wants=cluster-init.service

[Service]
Type=simple
User=jetson
Groups=video,crypto
WorkingDirectory=/home/jetson/llama.cpp
# MANDATORY per-node -m (Phase 7): Jetson is UMA (no discrete VRAM). Without -m,
# rpc-server reports only ~14 MB free and gets almost no layers. node0 keeps the
# GUI so gets a SMALLER buffer (3000) than the headless workers (3600).
# NOTE: this unit is the node0 (Nano Zero) template. Workers must use -m 3600.
ExecStart=/home/jetson/llama.cpp/build/bin/rpc-server --host 0.0.0.0 --port 50052 -m 3000

# Lifecycle & Self-Healing Policies
Restart=always
RestartSec=2s
StartLimitIntervalSec=30s
StartLimitBurst=5

# Memory Safety Limits (Triggers dynamic clean restarts before kernel panic)
MemoryAccounting=yes
MemoryMax=3850M
MemoryHigh=3700M
OOMPolicy=stop

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable llama-rpc.service

echo "[PHASE 7] Daemon configuration complete. RPC service enabled."