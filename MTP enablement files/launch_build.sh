cd /home/jetson/llama.cpp-mtp
setsid bash -c 'bash /home/jetson/build_mtp.sh > /home/jetson/mtp_build.log 2>&1' < /dev/null &
disown
echo "LAUNCHED pid=$!"
sleep 3
echo "=== immediate log check ==="
cat /home/jetson/mtp_build.log 2>&1 | head -20
echo "=== proc check ==="
pgrep -f build_mtp.sh >/dev/null && echo RUNNING || echo STOPPED
