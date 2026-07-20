#!/bin/bash
# probe_node0.sh - inspect rpc-server state on node0
ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=no jetson@192.168.50.150 'echo === PROCS ===; ps aux | grep -E "rpc-server|ggml-rpc-server" | grep -v grep; echo === STABLE BIN ===; ls -la /home/jetson/llama.cpp/build/bin/ 2>/dev/null | grep -E "rpc"; echo === MTP BIN ===; ls -la /home/jetson/llama.cpp-mtp/build/bin/ 2>/dev/null | grep -E "rpc"; echo === MTP BUILD DIR EXISTS? ===; ls -d /home/jetson/llama.cpp-mtp/build 2>/dev/null || echo NO_MTP_BUILD_DIR'
