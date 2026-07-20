#!/usr/bin/env bash
# Attempt to bring up the CSR Bluetooth dongle (hci0) on node0 (.150)
ssh -i /home/marti/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=no jetson@192.168.50.150 bash -s <<'EOF'
set -x
echo "=== BEFORE ==="
hciconfig hci0 2>/dev/null | grep -E 'hci|DOWN|UP' || echo "no-hci-info"

echo "=== TRY: hciconfig hci0 up ==="
sudo hciconfig hci0 up 2>&1
echo "rc=$?"

echo "=== TRY: bluetoothctl power on ==="
bluetoothctl power on 2>&1 | head -5

echo "=== AFTER ==="
hciconfig hci0 2>/dev/null | grep -E 'hci|DOWN|UP' || echo "no-hci-info"

echo "=== DMESG TAIL (post-attempt) ==="
dmesg 2>/dev/null | tail -15
EOF
