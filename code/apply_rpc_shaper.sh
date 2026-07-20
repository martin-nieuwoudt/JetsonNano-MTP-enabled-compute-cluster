#!/usr/bin/env bash
# apply_rpc_shaper.sh — idempotent per-node egress shaper for the RPC port.
# Part (A) of the anti-incast fix (Phase 12). Caps the RPC upload burst per node
# so a single Nano can never flood the small interconnect switch during the
# simultaneous weight-shard upload that caused the 2026-07-14 storm.
#
# Idempotent: clears any prior shaper on the iface first, then re-applies.
# Reads all tunables from cluster_config.py's ANTI-INCAST PACING block via env
# vars passed by the caller (llama-rpc-shape.service / install_rpc_service.sh):
#   RPC_SHAPER_IFACE  RPC_SHAPER_RATE  RPC_SHAPER_BURST  RPC_SHAPER_PORT
set -u
IFACE="${RPC_SHAPER_IFACE:-eth0}"
RATE="${RPC_SHAPER_RATE:-850mbit}"
BURST="${RPC_SHAPER_BURST:-64kb}"
PORT="${RPC_SHAPER_PORT:-50052}"

command -v tc >/dev/null 2>&1 || { echo "tc not found; skipping shaper"; exit 0; }

# --- clear any prior shaper on this iface (idempotent) ---
tc qdisc del dev "$IFACE" root 2>/dev/null || true

# --- root HTB classful qdisc ---
tc qdisc add dev "$IFACE" root handle 1: htb default 20
# --- class 1:1 = the rate cap (whole iface ceiling) ---
tc class add dev "$IFACE" parent 1: classid 1:1 htb rate "$RATE" ceil "$RATE"
# --- class 1:10 = RPC port, tight burst bucket to smooth incast spikes ---
tc class add dev "$IFACE" parent 1:1 classid 1:10 htb rate "$RATE" ceil "$RATE" burst "$BURST"
# --- filter: RPC port -> class 1:10 ---
tc filter add dev "$IFACE" parent 1: protocol ip u32 \
    match ip dport "$PORT" 0xffff flowid 1:10

echo "shaper applied: $IFACE port $PORT -> $RATE burst $BURST"
tc qdisc show dev "$IFACE"
