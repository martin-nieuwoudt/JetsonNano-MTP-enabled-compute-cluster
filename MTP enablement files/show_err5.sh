cd /home/jetson
echo "=== grep error in log ==="
grep -n -i "error\|undefined reference\|cannot find\|ld returned\|Error 1\|Error 2" /home/jetson/mtp_build.log | tail -30
echo ""
echo "=== tail 25 ==="
tail -25 /home/jetson/mtp_build.log
