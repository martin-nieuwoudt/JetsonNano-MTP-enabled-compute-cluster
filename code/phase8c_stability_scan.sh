#!/usr/bin/env bash
# Phase 8c — Pre-shutdown stability & efficiency scan (READ-ONLY, non-destructive)
# Run on node0. Reports thermal, kernel, systemd, memory, storage, process health.
set +e
echo "===== PHASE 8c STABILITY SCAN : $(hostname)  $(date -u +%FT%TZ) ====="

echo
echo "--- [A] THERMAL ---"
for f in /sys/devices/virtual/thermal/thermal_zone*/temp; do
  [ -r "$f" ] && printf "  %s = %d C\n" "$f" "$(( $(cat "$f") / 1000 ))"
done 2>/dev/null
echo "  thermal throttle events (cpu0):"
for f in /sys/devices/system/cpu/cpu0/thermal_throttle/*_throttle_count; do
  [ -r "$f" ] && printf "    %s = %s\n" "$(basename "$f")" "$(cat "$f")"
done 2>/dev/null
if command -v nvpmodel >/dev/null 2>&1; then
  printf "  nvpmodel: "; sudo -n nvpmodel -q 2>/dev/null || nvpmodel -q 2>/dev/null || echo "n/a"
fi

echo
echo "--- [B] KERNEL / DMESG ERRORS (last 30) ---"
dmesg -T 2>/dev/null | grep -iE 'error|warn|oom|kill|undervolt|thermal|mmc|ext4|fsck|reset|timeout' | tail -30 || echo "  (none)"

echo
echo "--- [C] SYSTEMD FAILED UNITS ---"
systemctl --failed --no-legend --no-pager 2>/dev/null || echo "  none"

echo
echo "--- [D] rpc-server PROCESS HEALTH ---"
ps -eo pid,ppid,stat,etime,%cpu,%mem,cmd 2>/dev/null | grep -E '[r]pc-server' || echo "  rpc-server NOT running"
echo "  jetson-maxperf restarts: $(systemctl show jetson-maxperf.service --property=NRestarts 2>/dev/null)"

echo
echo "--- [E] MEMORY PRESSURE / OOM ---"
free -m 2>/dev/null
echo "  OOM/kill in journal:"
journalctl -b -p err 2>/dev/null | grep -iE 'oom|killed process|out of memory' | tail -10 || echo "    none"

echo
echo "--- [F] SD / STORAGE HEALTH ---"
echo "  mmc/sdcard errors:"
dmesg -T 2>/dev/null | grep -iE 'mmc|sdcard' | grep -iE 'error|fail|timeout|currupted' | tail -10 || echo "    none"
df -h / 2>/dev/null | tail -1
df -i / 2>/dev/null | tail -1

echo
echo "--- [G] ZOMBIE / ORPHAN PROCESSES ---"
ps -eo pid,ppid,stat,comm 2>/dev/null | awk '$3 ~ /Z/ {print "  ZOMBIE:", $0}' || echo "  none"
echo "  top CPU consumers:"
ps -eo pid,%cpu,%mem,comm --sort=-%cpu 2>/dev/null | head -6

echo
echo "--- [H] JOURNAL ERRORS SINCE BOOT (last 20) ---"
journalctl -b -p err -n 20 --no-pager 2>/dev/null || echo "  none"

echo
echo "===== SCAN COMPLETE ====="
