#!/bin/bash
echo "== thermal zones =="
for z in /sys/devices/virtual/thermal/thermal_zone*; do
  t=$(cat "$z/temp" 2>/dev/null)
  echo "$z: $((t/1000)) C  type=$(cat "$z/type" 2>/dev/null)"
done
echo "== tegrastats one-shot =="
timeout 2 tegrastats --interval 1000 2>&1 | head -1
