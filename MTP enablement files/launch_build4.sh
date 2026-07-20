cd /home/jetson
nohup bash /home/jetson/build_mtp.sh > /home/jetson/mtp_build.log 2>&1 &
echo "build pid=$!"
sleep 5
head -3 /home/jetson/mtp_build.log
