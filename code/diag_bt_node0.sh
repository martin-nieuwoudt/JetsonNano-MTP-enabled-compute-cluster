#!/usr/bin/env bash
# Diagnose Bluetooth dongle on node0 (.150)
ssh -i /home/marti/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=no jetson@192.168.50.150 bash -s <<'EOF'
echo "=== USB DEVICES ==="
lsusb
echo
echo "=== DMESG (bt/usb/firmware) ==="
dmesg 2>/dev/null | grep -iE 'blue|btusb|firmware|usb.*error|usb.*fail' | tail -40
echo
echo "=== BLUETOOTH SERVICE ==="
systemctl is-active bluetooth 2>/dev/null || echo "no-systemd-or-inactive"
echo
echo "=== HCI CONFIG ==="
hciconfig -a 2>/dev/null || echo "no-hciconfig"
echo
echo "=== KERNEL MODULES (bt/usb) ==="
lsmod 2>/dev/null | grep -iE 'btusb|bluetooth|usbcore' || echo "no-bt-modules-listed"
echo
echo "=== OS / KERNEL ==="
uname -a
cat /etc/os-release 2>/dev/null | head -3
EOF
