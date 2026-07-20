#!/usr/bin/env bash
# Unblock Bluetooth via rfkill and bring hci0 up on node0 (.150)
ssh -i /home/marti/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=no jetson@192.168.50.150 bash -s <<'EOF'
set -x
echo "=== RFKILL LIST (before) ==="
rfkill list 2>&1

echo "=== RFKILL UNBLOCK ALL ==="
sudo rfkill unblock all 2>&1
echo "rc=$?"

echo "=== RFKILL LIST (after) ==="
rfkill list 2>&1

echo "=== HCI UP ==="
sudo hciconfig hci0 up 2>&1
echo "rc=$?"

echo "=== BLUETOOTHCTL POWER ON ==="
bluetoothctl power on 2>&1 | head -5

echo "=== HCI STATE ==="
hciconfig hci0 2>/dev/null | grep -E 'hci|DOWN|UP|BD Addr'

echo "=== SCAN TEST (5s) ==="
timeout 6 bluetoothctl scan on 2>&1 | head -10
bluetoothctl scan off 2>&1 | head -2
EOF
