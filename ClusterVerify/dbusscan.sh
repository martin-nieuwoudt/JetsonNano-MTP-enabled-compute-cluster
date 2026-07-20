#!/bin/bash
KEY=/root/.ssh/id_ed25519
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=10 -o BatchMode=yes"
NODE=jetson@192.168.50.151

ssh $OPTS $NODE '
echo "=== scan system.d for non-XML (corrupted) files ==="
for f in /usr/share/dbus-1/system.d/*.conf; do
  magic=$(sudo head -c 1 "$f" 2>/dev/null)
  if [ "$magic" != "<" ]; then
    echo "CORRUPT: $f  (first byte: $(sudo head -c 4 "$f" | xxd | head -1))"
  fi
done
echo "=== scan session.d too ==="
for f in /usr/share/dbus-1/session.d/*.conf; do
  [ -e "$f" ] || continue
  magic=$(sudo head -c 1 "$f" 2>/dev/null)
  if [ "$magic" != "<" ]; then
    echo "CORRUPT: $f"
  fi
done
echo "=== does basic systemctl work over the bus now? ==="
sudo systemctl list-units --type=service --no-pager 2>&1 | head -5 || echo "systemctl still broken"
echo "=== is NetworkManager running? ==="
pgrep -a NetworkManager 2>&1 || echo "NetworkManager NOT running"
'
