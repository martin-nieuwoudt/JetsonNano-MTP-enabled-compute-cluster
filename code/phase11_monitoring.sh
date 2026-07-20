#!/bin/bash
# Phase 11: Hardware Telemetry & Remote Access Agents (Template Node)
# From: Refinements.md Phase 0/3 — refined dependency list for this rebuild scenario.
# Run on the template Jetson Nano via SSH AFTER Phase 5 (binary built) and Phase 7 (daemon).
#
# All agent installs are COMMENTED OUT by default. Uncomment the block(s) you
# want per-node. Cloud agents (Datadog, SocketXP) require credentials at deploy
# time — set the env vars below before running, or fill them in directly.
#
# Credentials (set before running, or hardcode if scripting per-node):
#   export DD_API_KEY="<your-datadog-api-key>"
#   export DD_SITE="datadoghq.com"          # or datadoghq.eu etc.
#   export SOCKETXP_TOKEN="<your-socketxp-device-token>"

set -e
echo "[PHASE 11] Preparing hardware telemetry & remote-access agents..."

# ---------------------------------------------------------------------------
# OPTION A: Datadog IoT Agent (ARM64) — native Tegra hardware telemetry
#   Tracks GPU utilisation, dedicated memory distribution, thermal thresholds,
#   and external memory controller (EMC) bandwidth — metrics cluster_health.py
#   cannot read directly. Requires DD_API_KEY + DD_SITE.
# ---------------------------------------------------------------------------
# export DD_API_KEY="${DD_API_KEY:?set DD_API_KEY}"
# export DD_SITE="${DD_SITE:-datadoghq.com}"
# DD_INSTALLER="$(mktemp -d)/dd-iot.sh"
# curl -sL https://s3.amazonaws.com/dd-agent/scripts/install_iot.sh -o "$DD_INSTALLER"
# sudo DD_API_KEY="$DD_API_KEY" DD_SITE="$DD_SITE" bash "$DD_INSTALLER"
# sudo datadog-agent integration install -t datadog-jetson-nano==1.0.0 || true
# sudo systemctl enable --now datadog-agent

# ---------------------------------------------------------------------------
# OPTION B: SocketXP IoT Agent (ARM64) — secure reverse-tunnel SSH
#   Creates an encrypted tunnel to bypass NAT/firewall without opening public
#   ports. Requires SOCKETXP_TOKEN from socketxp.com.
# ---------------------------------------------------------------------------
# export SOCKETXP_TOKEN="${SOCKETXP_TOKEN:?set SOCKETXP_TOKEN}"
# curl -sL https://portal.socketxp.com/download/arm64/linux/socketxp -o /tmp/socketxp
# sudo install -m 0755 /tmp/socketxp /usr/local/bin/socketxp
# sudo socketxp login "$SOCKETXP_TOKEN"
# sudo socketxp connect tcp://localhost:22 --name jetson-$(hostname) || true

# ---------------------------------------------------------------------------
# OPTION C: Telegraf (ARM64) — self-hosted metrics (no cloud account)
#   Pushes Jetson telemetry to an InfluxDB you control. Alternative to Datadog.
# ---------------------------------------------------------------------------
# TELEGRAF_DEB="$(mktemp -d)/telegraf.deb"
# curl -sL "https://dl.influxdata.com/telegraf/releases/telegraf_1.30.0-1_arm64.deb" -o "$TELEGRAF_DEB"
# sudo apt install -y "$TELEGRAF_DEB"
# sudo systemctl enable --now telegraf

# ---------------------------------------------------------------------------
# OPTION D: Eclipse Mosquitto (MQTT broker) — IPC telemetry bus
#   Run on the Master PC (or a dedicated master node) to aggregate node
#   telemetry streams. Listed here for completeness; install on the PC side.
# ---------------------------------------------------------------------------
# sudo apt install -y mosquitto mosquitto-clients
# sudo systemctl enable --now mosquitto

echo "[PHASE 11] No agents installed (all blocks commented). Uncomment desired"
echo "[PHASE 11] blocks above and re-run, supplying credentials where required."
