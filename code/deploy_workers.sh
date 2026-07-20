#!/usr/bin/env bash
set -u
HOST_TGZ=/mnt/c/Users/marti/Desktop/Cluster/_symdl/mtp_bin.tgz
mkdir -p /mnt/c/Users/marti/Desktop/Cluster/_symdl

echo "=== [1/3] tar proven worker bin on .150 ==="
ssh -o BatchMode=yes jetson@192.168.50.150 'tar czf /tmp/mtp_bin.tgz -C /home/jetson/llama.cpp-mtp/build bin && echo tarred $(du -h /tmp/mtp_bin.tgz | cut -f1)'

echo "=== [2/3] pull to WSL host ==="
scp -o BatchMode=yes jetson@192.168.50.150:/tmp/mtp_bin.tgz "$HOST_TGZ" && echo "pulled $(du -h "$HOST_TGZ" | cut -f1)"

echo "=== [3/3] push + extract + restart on drifted nodes ==="
for n in 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$n"
  scp -o BatchMode=yes "$HOST_TGZ" jetson@$ip:/tmp/mtp_bin.tgz >/dev/null 2>&1
  res=$(ssh -o BatchMode=yes jetson@$ip '
    tar xzf /tmp/mtp_bin.tgz -C /home/jetson/llama.cpp-mtp &&
    sudo systemctl restart llama-rpc.service &&
    sleep 2 &&
    b=$(stat -c %y /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server | cut -d. -f1) &&
    p=$(pgrep -af ggml-rpc-server | head -1) &&
    echo "bin=$b proc=$p"
  ' 2>&1)
  echo "$ip -> $res"
done
echo "=== DONE ==="
