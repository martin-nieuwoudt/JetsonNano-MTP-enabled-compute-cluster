#!/usr/bin/env bash
for i in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$i"
  if ssh -o BatchMode=yes "jetson@$ip" 'sudo systemctl restart llama-rpc.service' >/dev/null 2>&1; then
    echo "$ip restarted"
  else
    echo "$ip FAILED"
  fi
done
