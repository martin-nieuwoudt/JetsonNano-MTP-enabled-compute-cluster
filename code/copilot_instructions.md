# GitHub Copilot Instructions for Jetson Nano Cluster Context
# From: raw refinements.md — Section: Forcing Copilot to Respect Legacy Hardware Constraints
# Place in .github/copilot-instructions.md in workspace root, or paste into
# Copilot Chat system prompt instructions.

You are diagnosing a bare-metal 10-node Jetson Nano cluster.
Hardware Architecture: Maxwell GPU (Compute Capability 5.3). 
Memory Constraint: 4GB LPDDR4 Unified Memory Architecture (UMA) shared between CPU/GPU.
Operating System: JetPack 4.6.x (Ubuntu 18.04).
CUDA Version: 10.2.
Network Architecture: 1GbE Star Topology managed via llama.cpp RPC.
Strict Rules: 
- DO NOT suggest modern CUDA features (no Half-Precision bfloat16, no Tensor Cores).
- Only optimize using FP16 precision.
- Use legacy nvprof syntax, not modern Nsight Compute CLI commands.
- Assume nvidia-smi does not exist; use tegrastats or jtop APIs for telemetry.