#!/usr/bin/env bash
for n in 155 156 159 160; do
  ip="192.168.50.$n"
  echo -n "$ip MemAvailable: "
  timeout 6 ssh -o BatchMode=yes jetson@$ip 'awk "/MemAvailable/{printf \"%.0f MB\n\", $2/1024}" /proc/meminfo' 2>/dev/null
done
