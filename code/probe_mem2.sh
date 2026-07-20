#!/bin/bash
# probe_mem2.sh - raw MemFree/Cached/SReclaimable (KB) across fleet
for i in $(seq 150 160); do
  ip="192.168.50.$i"
  out=$(ssh -o BatchMode=yes -o ConnectTimeout=6 -o StrictHostKeyChecking=no jetson@$ip \
    'awk "/MemFree/ {f=\$2} /^Cached/ {c=\$2} /SReclaimable/ {s=\$2} END {print f, c, s}" /proc/meminfo' 2>&1)
  printf "%s  FREE=%sMB CACHED=%sMB SLAB=%sMB\n" "$ip" $(echo $out | awk '{print int($1/1024)}') $(echo $out | awk '{print int($2/1024)}') $(echo $out | awk '{print int($3/1024)}')
done
