#!/bin/bash
KEY=/root/.ssh/id_ed25519
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
NODE=jetson@192.168.50.151

ssh $OPTS $NODE 'bash -s' <<'EOF' 2>&1
echo "=== tegrastats direct (background + sleep) ==="
tegrastats > /tmp/tegra_out.txt 2>/tmp/tegra_err.txt &
TPID=$!
sleep 2
kill $TPID 2>/dev/null
echo "--- stdout ---"; head -2 /tmp/tegra_out.txt
echo "--- stderr ---"; head -2 /tmp/tegra_err.txt
echo "=== which timeout ==="
which timeout; timeout --help 2>&1 | head -2
echo "=== GNU timeout test ==="
/usr/bin/timeout 2 tegrastats --interval 1000 2>&1 | head -1 || echo "rc=$?"
EOF
