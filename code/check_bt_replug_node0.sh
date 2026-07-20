#!/usr/bin/env bash
# Re-check CSR Bluetooth dongle state on node0 (.150) after replug
ssh -i /home/marti/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=no jetson@192.168.50.150 bash -s <<'EOF'
set -x
echo "=== USB ==="
lsusb | grep -iE 'cambridge|blue|0a12'
echo "=== RFKILL ==="
rfkill list 2>&1
echo "=== HCI STATE ==="
hciconfig hci0 2>/dev/null | grep -E 'hci|UP|DOWN|BD Addr|RUNNING' || echo "no-hci"
echo "=== IF DOWN, FIX ==="
sudo rfkill unblock all 2>&1
sudo hciconfig hci0 up 2>&1
echo "=== FINAL ==="
hciconfig hci0 2>/dev/null | grep -E 'hci|UP|DOWN|RUNNING'
EOF
