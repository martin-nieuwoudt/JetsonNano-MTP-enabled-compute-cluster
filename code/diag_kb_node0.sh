#!/usr/bin/env bash
# Diagnose the keyboard/mouse wireless dongle on node0 (.150)
ssh -i /home/marti/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=no jetson@192.168.50.150 bash -s <<'EOF'
set -x
echo "=== USB (all, with kernel driver) ==="
lsusb -t 2>/dev/null || lsusb
echo
echo "=== DMESG tail (usb/hid/input) ==="
dmesg 2>/dev/null | grep -iE 'usb|hid|input|logitech|unifying|receiver' | tail -40
echo
echo "=== INPUT DEVICES (keyboard/mouse) ==="
ls -1 /dev/input/by-id/ 2>/dev/null || echo "no /dev/input/by-id"
echo "---"
ls -1 /dev/input/ 2>/dev/null
echo
echo "=== HID MODULES ==="
lsmod 2>/dev/null | grep -iE 'hid|usbhid|logitech' || echo "no-hid-modules-listed"
echo
echo "=== UDEV monitor (5s plug re-scan) ==="
sudo udevadm monitor --environment --subsystem-match=input 2>/dev/null &
MON=$!
sleep 5
kill $MON 2>/dev/null
EOF
