#!/usr/bin/env bash
ok=0; bad=0
for n in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$n"
  r=$(ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no jetson@$ip \
    'ss -ltnp 2>/dev/null | grep -q ":50052" && echo UP || echo DOWN' 2>&1)
  bin=$(ssh -o BatchMode=yes -o ConnectTimeout=8 -o StrictHostKeyChecking=no jetson@$ip \
    'stat -c %y /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server 2>/dev/null | cut -d. -f1' 2>&1)
  if [ "$r" = "UP" ]; then ok=$((ok+1)); else bad=$((bad+1)); fi
  printf "%s : %s  (bin mtime %s)\n" "$ip" "$r" "$bin"
done
echo "----"
echo "UP=$ok  DOWN=$bad  / 11 total"
