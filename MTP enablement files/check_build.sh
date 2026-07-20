echo "=== full error lines from build log ==="
grep -n "error:" /home/jetson/mtp_build.log
echo ""
echo "=== context around first error ==="
grep -n "error:" /home/jetson/mtp_build.log | head -1 | cut -d: -f1 | while read ln; do
  start=$((ln-15)); [ $start -lt 1 ] && start=1
  sed -n "${start},$((ln+5))p" /home/jetson/mtp_build.log
done
