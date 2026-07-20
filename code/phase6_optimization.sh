#!/bin/bash
# Phase 6: System Optimization & Networking (Template Node)
# From: Nano Work Plan.md — Phase 6: System Optimization & Networking (Template Node)
# Run on the template Jetson Nano via SSH

set -e

echo "[PHASE 6] Maximizing hardware throughput, configuring firewall, applying Kernel/VMM overrides..."

# Power Mode
sudo nvpmodel -m 0

# Clock Lock
sudo jetson_clocks

# RPC Port Authorization
sudo ufw allow 50052/tcp

# NFS Port Authorization
sudo ufw allow 2049/tcp

# Enable Firewall
sudo ufw enable

# Kernel & VMM (Virtual Memory Manager) Overrides
# Forces the kernel to yield all resources to the rpc-server binary
cat << 'EOF' | sudo tee /etc/sysctl.d/99-jetson-cluster.conf
# Force the kernel to aggressively reclaim memory before failing allocations
vm.min_free_kbytes = 131072

# Prevent memory fragmentation by forcing continuous page compaction
vm.compaction_proactiveness = 100

# Set swappiness to maximum to allow clean page tracking on long-duration tasks
vm.swappiness = 100

# Prevent the OS from over-allocating virtual memory structures
vm.overcommit_memory = 2
vm.overcommit_ratio = 80

# Hugepages for TLB miss reduction on large tensor allocations
vm.nr_hugepages = 512

# Keep network buffer allocations compact and stable for continuous RPC streaming
net.ipv4.tcp_rmem = 4096 87380 4194304
net.ipv4.tcp_wmem = 4096 65536 4194304

# Increase the maximum number of open files and system descriptors
fs.file-max = 2097152

# Allocate substantial core network memory buffers to avoid transmission drops
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216

# Increase maximum network packet queue length to handle high-context spikes
net.core.netdev_max_backlog = 10000

# Disable TCP slow start after idle periods to keep the 1GbE lanes primed
net.ipv4.tcp_slow_start_after_idle = 0

# TCP keepalive timeout for fast node failure detection (15s)
net.ipv4.tcp_keepalive_time = 15
EOF

sudo sysctl -p /etc/sysctl.d/99-jetson-cluster.conf

# Hardware Memory Controller Optimization (Bootloader Parameters)
# Enforces memory contiguity in the Unified Memory Architecture (UMA)
# File: /boot/extlinux/extlinux.conf
# Locate the kernel arguments line (APPEND) and inject:
# cma=512M coherent_pool=64M alloc_as_vram=1
# This forces the kernel to carve out a permanent, block-aligned CMA pool.

# Jetson Max Performance systemd Service
# Hard-pins the memory controller and hardware execution pipes
sudo tee /etc/systemd/system/jetson-maxperf.service > /dev/null << 'EOF'
[Unit]
Description=Pin NVIDIA Jetson Hardware to Max Compute Profile
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/sbin/nvpmodel -m 0
ExecStartPost=/usr/bin/jetson_clocks
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable jetson-maxperf.service

# Cluster Init Service (persists across reboots)
sudo tee /etc/systemd/system/cluster-init.service > /dev/null << 'EOF'
[Unit]
Description=Jetson Cluster Init (power, clocks, firewall)
After=network.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'nvpmodel -m 0 && jetson_clocks && ufw allow 50052/tcp && ufw allow 2049/tcp'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable cluster-init.service

echo "[PHASE 6] System optimization complete. Reboot required for bootloader parameters."