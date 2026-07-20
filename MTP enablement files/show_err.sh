cd /home/jetson
echo "=== grep for Error / error in log ==="
grep -n -i "error\|Error 1\|Error 2\|undefined reference\|cannot find\|ld returned" /home/jetson/mtp_build.log | tail -40
echo ""
echo "=== tail 40 of log ==="
tail -40 /home/jetson/mtp_build.log
