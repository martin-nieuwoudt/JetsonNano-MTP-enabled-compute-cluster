# Agent Swarm — MTP CUDA C++17→C++14 Port
# Deploys parallel agents that each own a shard of CUDA files on node0
# (192.168.50.150, user jetson). Each agent edits over SSH/SCP.
#
# Two parallel backends (per user choice "Both in parallel"):
#   A) CopilotSwarm extension  -> VS Code command: copilot-swarm.openPanel
#   B) OpenRouter free models   -> this harness (BLOCKED until OR key present, see below)
#
# Reference docs the agents must read FIRST:
#   C:\Users\marti\Desktop\Cluster\C++\n4140.pdf   (C++14 standard - the TARGET)
#   C:\Users\marti\Desktop\Cluster\C++\n4659.pdf   (C++17 draft - what is NOT allowed)
#   C:\Users\marti\Desktop\Cluster\llamita_ref\PATCHES.md  (proven port methodology)
#   C:\Users\marti\Desktop\Cluster\MTP CUDA Enablement Work Plan.md
#   C:\Users\marti\Desktop\Cluster\MTP_CUDA_STATUS.md

NODE0="jetson@192.168.50.150"
SRC="/home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda"
WSL="wsl -d Ubuntu -e bash -c"

# --- Shard 1: common.cuh (CRITICAL PATH, blocks everything) ---
# Owner: best reasoning model. Do NOT stub binbcast logic.
# Fixes: std::is_same_v -> std::is_same<T,Ts>::value
#        if constexpr(C) -> if (C)  (discarded branches hold only static_assert)
SHARD1="common.cuh"

# --- Shard 2: convert.cuh + BF16 intrinsic shim ---
SHARD2="convert.cuh vendors/cuda_bf16.h vendors/cuda.h"

# --- Shard 3: gated_delta_net.cu (3 if constexpr at 84/145/160) ---
SHARD3="gated_delta_net.cu"

# --- Shard 4: remaining MTP-only .cu/.cuh (from onlymtp_files.txt) ---
SHARD4="col2im-1d.cu col2im-1d.cuh fwht.cu fwht.cuh snake.cu snake.cuh mmq-instance-nvfp4.cu"

# --- Shard 5: fattn-* / mmq / mmvq / rope / norm / concat / topk-moe / mma / etc ---
SHARD5="fattn.cu fattn-mma-f16.cuh fattn-tile.cuh fattn-vec.cuh fattn-common.cuh mmq.cuh mmq.cu mmvq.cu rope.cu norm.cu concat.cu topk-moe.cu mma.cuh mmf.cuh mmvf.cu mmid.cu tri.cu binbcast.cu"

# Pull a file to local temp for an agent to inspect/edit, then push back.
pull() { $WSL "scp -o BatchMode=yes $NODE0:$SRC/$1 /mnt/c/Users/marti/Desktop/Cluster/_work/$1"; }
push() { $WSL "scp -o BatchMode=yes /mnt/c/Users/marti/Desktop/Cluster/_work/$1 $NODE0:$SRC/$1"; }

echo "Swarm shards defined. Launch CopilotSwarm panel for backend A,"
echo "then assign each shard above to one agent. Backend B (OpenRouter)"
echo "is BLOCKED: no OPENROUTER_API_KEY / config found on this machine."
echo "Provide a key to enable it."
