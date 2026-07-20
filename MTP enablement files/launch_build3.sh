cd /home/jetson
echo "=== relaunch build ==="
nohup bash /home/jetson/build_mtp.sh > /home/jetson/mtp_build.log 2>&1 &
echo "build pid=$!"
sleep 5
echo "=== first lines of log ==="
head -20 /home/jetson/mtp_build.log
