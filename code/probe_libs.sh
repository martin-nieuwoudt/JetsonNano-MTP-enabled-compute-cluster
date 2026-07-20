#!/usr/bin/env bash
timeout 8 ssh -o BatchMode=yes jetson@192.168.50.150 '
  echo "--- ldd (libggml deps) ---"
  ldd /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server 2>/dev/null | grep -iE "ggml|not found" 
  echo "--- lib dir ---"
  ls -la /home/jetson/llama.cpp-mtp/build/bin/libggml* 2>/dev/null
  echo "--- service file ---"
  systemctl cat llama-rpc.service 2>/dev/null | grep -iE "ExecStart|WorkingDirectory" | head -3
' 2>&1
