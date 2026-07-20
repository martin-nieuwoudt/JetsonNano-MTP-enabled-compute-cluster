#!/bin/bash
# Phase 10: Execution (Windows Master PC)
# From: Nano Work Plan.md — Phase 10: Execution (Windows Master PC)
# Run on Windows 11 Master PC (PowerShell)

# Mandatory Flag: --flash-attn in all launch strings

# Target Models (70B-class dense, IQ3_XS ~29.5 GB):
# Qwen 2.5 72B Instruct (IQ3_XS) — Top choice for coding: tracks bracket balance, syntax, indentation with high precision even at 3-bit.
# Llama 3.3 70B Instruct (IQ3_XS) — Top choice for hard reasoning & agentic function-calling.

# Reject MoE variants — distributing sparse expert layers over network switches creates erratic latency spikes every time a different expert activates.

# Architecture: PC → All 11 Nanos (direct star topology RPC). Nano Zero serves model weights from SSD via NFS for pre-seeding (not in inference data path).

# Full Cluster (Single Instance, 70B dense):
# The PC is a CPU-only RPC CLIENT (llama-cli.exe), NOT a CUDA llama-server.
# The Nano nodes run rpc-server (Phase 5/7). The model is sliced on the PC and
# the Maxwell GPU compute happens on the Nanos.
# .\build\bin\llama-cli.exe -m C:\Models\Qwen2.5-72B-Instruct-IQ3_XS.gguf --flash-attn --rpc 192.168.50.150:50052,192.168.50.151:50052,192.168.50.152:50052,192.168.50.153:50052,192.168.50.154:50052,192.168.50.155:50052,192.168.50.156:50052,192.168.50.157:50052,192.168.50.158:50052,192.168.50.159:50052,192.168.50.160:50052 --tensor-split 0.85,1,1,1,1,1,1,1,1,1,1 --ctx-size 8192

# Smoke test (proven 2026-07-10, single node):
# .\build\bin\llama-cli.exe -m C:\Models\tiny_test\qwen0.5b-q4km.gguf -p "Hello" -n 20 --rpc 192.168.50.150:50052

# Note: 70B IQ3_XS models require all 11 nodes (~33-35 GB usable pool). No sub-cluster configuration is viable at this size — the model won't fit on fewer than 10 nodes. The earlier sub-cluster grouping (3 nodes each) was designed for Gemma 4 12B (~7 GB) and is not applicable to 70B deployments.