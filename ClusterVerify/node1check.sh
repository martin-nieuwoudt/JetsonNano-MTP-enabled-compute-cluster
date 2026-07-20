#!/bin/bash
ssh -i /root/.ssh/id_ed25519 \
  -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
  -o ConnectTimeout=10 -o BatchMode=yes \
  jetson@192.168.50.151 \
  'echo RAM=$(grep MemAvailable /proc/meminfo); echo RPC=$(pgrep -c rpc-server); echo SSHD=$(pgrep -c sshd); echo SELFHEAL=$(ls /usr/local/bin/cluster-selfheal.sh 2>/dev/null | wc -l); echo DEFAULT=$(readlink /etc/systemd/system/default.target)'
