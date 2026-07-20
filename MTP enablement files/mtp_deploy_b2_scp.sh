#!/bin/bash
# Step 2 (fixed): copy tar FROM node0 TO each target node, then extract + launch
NODES="151 152 153"
for n in $NODES; do
  ip="192.168.50.$n"
  echo "=== node .$n ==="
  ssh -o BatchMode=yes jetson@$ip 'bash -s' <<INNER
    mkdir -p /home/jetson/llama.cpp-mtp/build/bin
    pkill -f 'ggml-rpc-server.*50053' 2>/dev/null || true
INNER
  ssh -o BatchMode=yes jetson@192.168.50.150 "scp -o BatchMode=yes /tmp/mtp_worker.tgz jetson@$ip:/tmp/mtp_worker.tgz"
  ssh -o BatchMode=yes jetson@$ip 'bash -s' <<INNER
    set -e
    cd /home/jetson/llama.cpp-mtp/build/bin
    tar xzf /tmp/mtp_worker.tgz
    ln -sf libggml-base.so.0.15.3 libggml-base.so.0
    ln -sf libggml-base.so.0 libggml-base.so
    ln -sf libggml-cpu.so.0.15.3  libggml-cpu.so.0
    ln -sf libggml-cpu.so.0  libggml-cpu.so
    ln -sf libggml-cuda.so.0.15.3 libggml-cuda.so.0
    ln -sf libggml-cuda.so.0  libggml-cuda.so
    ln -sf libggml-rpc.so.0.15.3  libggml-rpc.so.0
    ln -sf libggml-rpc.so.0  libggml-rpc.so
    ln -sf libggml.so.0.15.3     libggml.so.0
    ln -sf libggml.so.0     libggml.so
    chmod +x ggml-rpc-server
    nohup ./ggml-rpc-server -H 0.0.0.0 -p 50053 -t 2 > /home/jetson/mtp_rpc_$n.log 2>&1 &
    sleep 2
    echo "launched pid $(pgrep -f 'ggml-rpc-server.*50053')"
INNER
done
echo "=== DONE ==="
