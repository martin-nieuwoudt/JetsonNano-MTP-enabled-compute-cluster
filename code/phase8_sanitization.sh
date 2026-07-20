#!/bin/bash
# Phase 8: Identity Sanitization & Worker Baseline Finalization
# From: Nano Work Plan.md — Phase 8: Identity Sanitization & Worker Baseline Finalization
# Run on the template Jetson Nano via SSH

set -e

echo "[PHASE 8] Sanitizing identity for fleet cloning..."

# Purge Cryptographic Identity
sudo rm -f /etc/ssh/ssh_host_*

# Machine ID Reset
sudo rm -f /etc/machine-id
sudo rm -f /var/lib/dbus/machine-id

# Force systemd Machine ID Regeneration
sudo truncate -s 0 /etc/machine-id

# Vacuum Logs
sudo journalctl --vacuum-time=1s

# Vacuum Cache
sudo apt clean

# Wipe History
history -c

echo "[PHASE 8] Identity sanitization complete. Worker Baseline Image ready for cloning."
echo "NOTE: Each clone will regenerate unique SSH host keys and machine-id on first boot."
echo "Passwordless sudo is preserved in the image."