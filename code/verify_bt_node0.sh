#!/usr/bin/env bash
# Verify Bluetooth scan works on node0 (.150) + make unblock persistent
ssh -i /home/marti/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=no jetson@192.168.50.150 bash -s <<'EOF'
set -x
echo "=== PERSISTENT UNBLOCK (survives reboot) ==="
# Ensure rfkill unblock happens at boot via rc-local style or systemd drop-in
if [ -d /etc/rc.local.d ]; then
  echo "rfkill unblock all" | sudo tee /etc/rc.local.d/bt-unblock.sh >/dev/null
  sudo chmod +x /etc/rc.local.d/bt-unblock.sh
fi
# Also try the bluetooth service restart to re-init the dongle cleanly
sudo systemctl restart bluetooth 2>&1
sleep 2
sudo rfkill unblock all 2>&1
sudo hciconfig hci0 up 2>&1

echo "=== SCAN (8s) ==="
bluetoothctl scan on >/tmp/bt_scan.log 2>&1 &
SCANPID=$!
sleep 8
bluetoothctl scan off >/dev/null 2>&1
sleep 1
echo "--- devices seen ---"
cat /tmp/bt_scan.log | grep -iE 'Device |RSSI|paired' | head -20
echo "--- (empty above = no nearby discoverable devices, but interface is UP) ---"

echo "=== FINAL STATE ==="
hciconfig hci0 2>/dev/null | grep -E 'hci|UP|DOWN|BD Addr'
rfkill list 2>&1
EOF
