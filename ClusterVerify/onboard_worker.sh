#!/bin/bash
# onboard_worker.sh <N> — onboard Jetson worker N (1..10) into the 11-node cluster.
#
# Usage:  bash onboard_worker.sh 3     # -> nano03 @ 192.168.50.153
#
# CRITICAL (learned 2026-07-13):
#   The PC private key the nodes trust is /home/marti/.ssh/id_ed25519_vm
#   (fingerprint SHA256:clQngg9C...). The default id_ed25519 is a MISMATCHED
#   key (ICYU4e2z...) and is REJECTED. Always use id_ed25519_vm.
#
#   Flashed worker images have PASSWORD AUTH OFF (key-only, set in phase6),
#   so push_keys.sh (sshpass+password) cannot bootstrap them. If a fresh node
#   does not yet trust the PC key, the script prints a one-line command for the
#   user to paste on the node console, then exits. Re-run after pasting.
#
# Idempotent and reboot-free where possible.
set -u
N="${1:?usage: onboard_worker.sh <worker_number 1..10>}"
[ "$N" -ge 1 ] && [ "$N" -le 10 ] || { echo "N must be 1..10"; exit 1; }

IP="192.168.50.$((150 + N))"
NAME="nano$(printf '%02d' "$N")"
KEY=/home/marti/.ssh/id_ed25519_vm
OPTS="-i $KEY -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes"
TARGET="jetson@$IP"

echo "=== Onboarding $NAME ($IP) ==="

# 0. Connectivity / key-trust check
if ! ssh $OPTS $TARGET "true" 2>/dev/null; then
  PUB="$(ssh-keygen -y -P "" -f "$KEY")"
  echo "!! SSH denied — $NAME does not yet trust the PC key."
  echo "   On the node console, run this ONCE:"
  echo "   echo '$PUB' >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && echo KEY_ADDED"
  echo "   Then re-run:  bash onboard_worker.sh $N"
  exit 2
fi
echo "SSH_OK"

# 1-5. Sanitize identity + verify (single remote session, no quoting hell)
ssh $OPTS $TARGET 'bash -s' <<PAYLOAD
set -e
echo "=== [1] hostname ==="
sudo hostnamectl set-hostname $NAME
echo "hostname=$(hostname)"
echo "=== [2] static IP $IP ==="
sudo nmcli con mod "Wired connection 1" ipv4.method manual ipv4.addresses $IP/24 ipv4.gateway 192.168.50.1 ipv4.dns 192.168.50.1
sudo nmcli con up "Wired connection 1"
ip -br addr show eth0
echo "=== [3] ssh host keys ==="
if ! ls /etc/ssh/ssh_host_ed25519_key >/dev/null 2>&1; then
  sudo rm -f /etc/ssh/ssh_host_*
  sudo ssh-keygen -t ed25519 -f /etc/ssh/ssh_host_ed25519_key -N '' -C $NAME
  sudo ssh-keygen -t rsa -b 4096 -f /etc/ssh/ssh_host_rsa_key -N '' -C $NAME
  sudo ssh-keygen -t ecdsa -b 521 -f /etc/ssh/ssh_host_ecdsa_key -N '' -C $NAME
  echo "host keys REGENERATED"
else
  echo "host keys PRESENT"
fi
echo "=== [4] machine-id (unique) ==="
sudo rm -f /etc/machine-id
sudo systemd-machine-id-setup
echo "machine-id=$(cat /etc/machine-id)"
echo "=== [5] rpc-server ==="
pgrep -a rpc-server | head -1 || echo "rpc_NOT_running"
PAYLOAD

# 6. node0 -> worker RPC reachability (port 50052)
echo "=== [6] node0 -> $IP:50052 ==="
ssh $OPTS jetson@192.168.50.150 "timeout 3 bash -c \"echo > /dev/tcp/$IP/50052\" && echo NODE0_REACHES_$IP || echo NODE0_CANNOT_REACH_$IP" 2>&1

echo "=== $NAME onboarded ==="
