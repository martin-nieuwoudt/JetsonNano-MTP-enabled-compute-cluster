#!/bin/bash
# node_prep.sh — clone-safe prep for a freshly-flashed Jetson Nano worker
# ---------------------------------------------------------------------------
# Run ON the node (local console, or via ssh as 'jetson' with passwordless sudo).
# Idempotent. Safe to re-run.
#
# Usage:  sudo bash node_prep.sh <NODE_NUM> <STATIC_IP>
#   NODE_NUM  : e.g. 1  -> hostname nano01, IP .151
#   STATIC_IP : e.g. 192.168.50.151
#   (both optional; defaults below)
#
# CRITICAL LESSON (2026-07-12, cost us a dead-console recovery):
#   This image's ssh.service does NOT auto-run `ssh-keygen -A` on boot
#   (unit only does `sshd -t` then `sshd -D`). If you delete the host keys
#   and reboot, sshd has no keys -> port 22 "Connection refused" -> no SSH.
#   => ALWAYS regenerate host keys IN THE SAME SESSION, BEFORE any reboot.
#   The block below does rm + ssh-keygen -A + a hard verify before continuing.
# ---------------------------------------------------------------------------

set -euo pipefail

NODE_NUM="${1:-1}"
STATIC_IP="${2:-192.168.50.151}"
GATEWAY="192.168.50.1"
DNS="192.168.50.1"
CONN="Wired connection 1"
HOSTNAME="nano$(printf '%02d' "$NODE_NUM")"

echo ">>> node_prep: target hostname=$HOSTNAME  ip=$STATIC_IP"

echo "=== [1/6] strip GUI -> headless (multi-user.target) ==="
sudo systemctl set-default multi-user.target

echo "=== [2/6] wipe + REGENERATE ssh host keys (same session!) ==="
sudo rm -f /etc/ssh/ssh_host_*
sudo ssh-keygen -A
# Hard guard: never proceed to reboot without keys present.
if ! ls /etc/ssh/ssh_host_*_key >/dev/null 2>&1; then
  echo "ERROR: host keys did not regenerate — ABORTING before reboot." >&2
  exit 1
fi
echo "host keys present: $(ls /etc/ssh/ | grep ssh_host_ | tr '\n' ' ')"

echo "=== [3/6] wipe machine-id (regenerate unique) ==="
sudo rm -f /etc/machine-id
sudo systemd-machine-id-setup
echo "new machine-id: $(cat /etc/machine-id)"

echo "=== [4/6] set unique hostname $HOSTNAME ==="
sudo hostnamectl set-hostname "$HOSTNAME"

echo "=== [5/6] set static IP $STATIC_IP (manual) ==="
sudo nmcli con mod "$CONN" \
  ipv4.method manual \
  ipv4.addresses "${STATIC_IP}/24" \
  ipv4.gateway "$GATEWAY" \
  ipv4.dns "$DNS"
sudo nmcli con up "$CONN"
ip -br addr show eth0

echo "=== [6/6] verify sshd is alive with keys BEFORE reboot ==="
sudo systemctl is-active ssh >/dev/null 2>&1 || sudo systemctl restart ssh
sudo systemctl is-active ssh
if ! ls /etc/ssh/ssh_host_*_key >/dev/null 2>&1; then
  echo "ERROR: no host keys at final check — DO NOT REBOOT." >&2
  exit 1
fi

echo "=== [7/8] HARDEN: SSH key-only (disable password auth) ==="
DROPIN=/etc/ssh/sshd_config.d/99-cluster-hardening.conf
if grep -q '^Include /etc/ssh/sshd_config.d' /etc/ssh/sshd_config; then
  sudo tee "$DROPIN" >/dev/null <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
PermitRootLogin no
EOF
  echo "WROTE drop-in $DROPIN"
else
  if ! sudo grep -q '^PasswordAuthentication no' /etc/ssh/sshd_config; then
    printf '\n# Cluster hardening (baked via node_prep)\nPasswordAuthentication no\nKbdInteractiveAuthentication no\nChallengeResponseAuthentication no\nPermitRootLogin no\n' | sudo tee -a /etc/ssh/sshd_config >/dev/null
  fi
  echo "APPENDED to main /etc/ssh/sshd_config"
fi
sudo sshd -t && echo "SSHD_CONFIG_VALID"
sudo systemctl restart ssh
sleep 1
sudo sshd -T 2>/dev/null | grep -i '^passwordauthentication'

echo "=== [8/8] HARDEN: firewall (ufw) ==="
# This kernel's ip6tables lacks the 'rt' match module, so the default
# before6.rules RH0-drop line fails to load and breaks the whole v6 ruleset.
# Strip it so ufw --enable succeeds and IPv6 is actually firewalled.
sudo sed -i '/-m rt --rt-type 0 -j DROP/d' /etc/ufw/before6.rules 2>/dev/null || true
sudo ufw allow 22/tcp
sudo ufw allow 50052/tcp
sudo ufw allow 2049/tcp
sudo ufw allow 111/tcp
sudo ufw --force enable
sleep 1
sudo ufw reload
sudo ufw status verbose | head -20

echo ">>> prep complete. Rebooting cleanly (host keys present, ssh key-only, ufw active)..."
sudo reboot
