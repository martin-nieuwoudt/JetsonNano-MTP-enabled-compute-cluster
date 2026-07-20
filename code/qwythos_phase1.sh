#!/bin/bash
# qwythos_phase1.sh - Phase-1 smoke test of Qwythos on b9886 fleet
RPC="192.168.50.150:50052,192.168.50.151:50052,192.168.50.152:50052,192.168.50.153:50052,192.168.50.154:50052,192.168.50.155:50052,192.168.50.156:50052,192.168.50.157:50052,192.168.50.158:50052,192.168.50.159:50052,192.168.50.160:50052"
PROMPT="You are the Strategist for the Anti-Dark-Forest research programme. State the core thesis of 'Biology as Bounded Information': that a civilisation which destroys or hides from others (the Dark Forest strategy) is thermodynamically and information-theoretically suboptimal compared with one that assimilates, simulates, and seeds. Then outline the six propositions P1 through P6 and, for each, name the simulation method that would test it."
C:/llama.cpp-mtp/build/bin/llama-cli.exe \
  -m "C:/Models/Qwythos-9B-Claude-Mythos-5-1M-BF16.gguf" \
  -p "$PROMPT" \
  -n 512 -c 4096 \
  --rpc "$RPC" \
  --no-display-prompt \
  --temp 0.7 --repeat-penalty 1.1 \
  -ngl 0
