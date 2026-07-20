#!/bin/bash
# Compare MTP build fingerprints across all 11 nodes against .150 reference.
REF_BIN="708480207958"
REF_CUDA="a3018793b086"
REF_GIT="20a04b220630"
echo "REF .150: bin=$REF_BIN cuda=$REF_CUDA git=$REF_GIT"
for n in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$n"
  out=$(ssh -i ~/.ssh/id_ed25519 -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no "jetson@$ip" 'B=$(sha256sum /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server 2>/dev/null | cut -c1-12); C=$(sha256sum /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/ggml-cuda.cu 2>/dev/null | cut -c1-12); G=$(cd /home/jetson/llama.cpp-mtp && git rev-parse HEAD 2>/dev/null | cut -c1-12); echo "bin=$B cuda=$C git=$G"' 2>&1)
  echo "$ip: $out"
done
