#!/bin/bash
KEY=/root/.ssh/id_ed25519
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
NODE=jetson@192.168.50.151

# Use head -1 SIGPIPE to terminate tegrastats (no busybox timeout dependency)
ssh $OPTS $NODE 'tegrastats --interval 1000 2>/dev/null | head -1' 2>&1
echo "EXIT=$?"
