#!/usr/bin/env bash
# Capture the FULL node-side journal for .157 around the allocation failure
ip=192.168.50.157
ssh -o BatchMode=yes "jetson@$ip" 'bash -s' <<'EOF'
echo "=== full recent journal for llama-rpc ==="
sudo journalctl -u llama-rpc.service -n 40 --no-pager
echo "=== is the service the MTP binary? ==="
cat /etc/systemd/system/llama-rpc.service 2>/dev/null | grep -E "ExecStart|WorkingDirectory"
EOF
