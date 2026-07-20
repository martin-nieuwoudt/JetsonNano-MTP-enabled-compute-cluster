#!/usr/bin/env bash
for i in 150 151 152 153 154 155 156 157 158 159 160; do
  r=$(ssh -o BatchMode=yes -o ConnectTimeout=4 -o StrictHostKeyChecking=no jetson@192.168.50.$i 'pgrep -a ggml-rpc-server || echo DOWN' 2>/dev/null)
  echo "$i: $r"
done
