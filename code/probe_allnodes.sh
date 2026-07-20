#!/usr/bin/env bash
for n in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$n"
  out=$(timeout 8 ssh -o BatchMode=yes jetson@$ip '
    b=/home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server
    m=$(stat -c %y "$b" 2>/dev/null | cut -d. -f1)
    if [ -d /home/jetson/llama.cpp-mtp/.git ]; then
      c=$(cd /home/jetson/llama.cpp-mtp && git rev-parse --short HEAD 2>/dev/null)
    else
      c="NO-GIT"
    fi
    p=$(pgrep -af ggml-rpc-server | head -1 | grep -oE "\-p [0-9]+" | awk "{print \$2}")
    echo "mtime=$m commit=$c port=${p:-?}"
  ' 2>/dev/null)
  echo "$ip -> ${out:-UNREACHABLE}"
done
