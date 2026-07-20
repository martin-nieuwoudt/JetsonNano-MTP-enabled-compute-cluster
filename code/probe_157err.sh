#!/usr/bin/env bash
# Show .157 node-side errors during the 11-node load (filter connect noise)
ssh -o BatchMode=yes jetson@192.168.50.157 'bash -s' <<'EOF'
sudo journalctl -u llama-rpc.service -n 30 --no-pager | grep -iE "error|fail|alloc|abort|oom|segfault|CUDA|out of memory" || echo "no error lines found"
EOF
