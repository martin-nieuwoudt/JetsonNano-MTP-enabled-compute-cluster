#!/usr/bin/env bash
ssh -o BatchMode=yes jetson@192.168.50.157 'bash -s' <<'EOF'
sudo journalctl -u llama-rpc.service -n 10 --no-pager | grep -iE "error|fail|alloc|cuda|oom"
EOF
