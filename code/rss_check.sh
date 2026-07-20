#!/usr/bin/env bash
for i in 150 151 152 153 154 155 156 157 158 159 160; do
  ip=192.168.50.$i
  rss=$(ssh -o BatchMode=yes -o ConnectTimeout=4 -o StrictHostKeyChecking=no jetson@$ip 'ps -o rss= -p $(pgrep -f rpc-server | head -1)' 2>/dev/null)
  rss=${rss:-0}
  mb=$(python3 -c "print(round($rss/1024,1))")
  printf '.%s (%s): %s MB\n' "$i" "$ip" "$mb"
done
