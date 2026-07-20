#!/bin/bash
# Remote launcher: kill any rpc-server, start MTP ggml-rpc-server detached.
pkill -f rpc-server 2>/dev/null
sleep 1
BIN=/home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server
setsid "$BIN" -H 0.0.0.0 -p 50052 -t 4 >/tmp/ggml-rpc.log 2>&1 < /dev/null &
echo "launched pid $!"
sleep 2
if ss -ltnp 2>/dev/null | grep -q ':50052'; then
  echo "LISTENING on 50052"
else
  echo "NOT_LISTENING"
  echo "--- log ---"
  cat /tmp/ggml-rpc.log 2>&1
fi
