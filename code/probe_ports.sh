#!/usr/bin/env bash
for n in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$n"
  p=$(ssh -o BatchMode=yes -o ConnectTimeout=4 jetson@$ip "ss -ltn 2>/dev/null | grep -oE ':5005[0-9]'")
  echo "$ip : $p"
done
