#!/bin/bash
# probe_node_cpu.sh - check ggml-rpc-server CPU/elapsed on all 11 nodes
for ip in 150 151 152 153 154 155 156 157 158 159 160; do
  line=$(ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no jetson@192.168.50.$ip 'ps -o pcpu,etime -C ggml-rpc-server --no-headers' 2>/dev/null | tr -d '\n')
  echo ".${ip}: ${line:-NO_PROC}"
done
