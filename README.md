# Jetson Nano 11-Node Cluster

An 11-node Jetson Nano (Maxwell SM 5.3, CUDA 10.2) compute cluster driven by a
Windows PC coordinator running a `llama.cpp`-based sharded-inference server plus
a telemetry dashboard. The cluster runs **MTP** (Multi-Token Prediction) models
(e.g. Qwythos-9B) across all 11 nodes via the `ggml-rpc-server` backend.

This repository is a **replicable build manual + the orchestration code** needed
to stand the cluster up from scratch and operate it.

## Documentation (the "bible")

Start here — these are the authoritative instructions:

| Document | Purpose |
|----------|---------|
| [`Nano Work Plan_Instructions.md`](Nano%20Work%20Plan_Instructions.md) | **Primary build manual.** Phase-by-phase from SD-card flash to live 11-node inference. Single source of truth for architecture and procedures. |
| [`MTP CUDA Enablement Work Plan.md`](Docs/MTP%20CUDA%20Enablement%20Work%20Plan.md) | The CUDA 10.2 / C++14 port of the MTP source tree that lets the Nano serve MTP models. |
| [`MTP_CUDA_STATUS.md`](Docs/MTP_CUDA_STATUS.md) | Live status & continuation doc for the MTP CUDA port. |
| [`Docs/`](Docs/) | Reference material, design notes, and status history. |

## Repository layout

```
code/                     Canonical orchestration scripts (dashboard, MCP server, deploy, QoS)
code/mcp/                 FastMCP server + single-source-of-truth config (RPC + Tier1 + Tier2 + model registry + power)
code/mcp/workers/         PyCUDA workers (GEMM, embedding, MoE ring) — SCP-pushed to Jetsons at runtime
code/pc_build/            PC build scripts (CPU+RPC, CUDA variants, nvcc tests)
code/methods/             Simulation-method library
ClusterVerify/            Cluster onboarding, verification, and diagnostics scripts
Docs/                     Instruction & reference docs (MTP work plan, MTP status)
MTP enablement files/     MTP CUDA port helpers, logs, and the 27 MTP-only file inventory
llamita_ref/              llamita.cpp upstream reference (CUDA 10.2 / 1-bit Bonsai)
mtp_pc_src/              MTP PC coordinator source — snapshot of C:\llama.cpp-mtp (commit 20a04b2, tag b9886) with the RPC buffer-probe patch applied
```

## Quick start

1. Read [`Nano Work Plan_Instructions.md`](Nano%20Work%20Plan_Instructions.md) end-to-end.
   It defines `CLUSTER_ROOT` (your working copy of this repo) and every changeable
   fact (node IPs, ports, model registry) lives in `code/mcp/cluster_config.py`.
2. Flash + bootstrap the nodes per Phases 1–9.
3. Build the PC coordinator: `C:\llama.cpp-mtp` (see Appendix B of the work plan).
   The PC is a CPU-only RPC client — CUDA compute runs on the Nanos only.
4. Build the MTP CUDA worker on node0 (see `MTP CUDA Enablement Work Plan.md`).
5. Launch the dashboard:
   ```
   C:\Python314\pythonw.exe code\cluster_telemetry.py web
   ```
   then open http://localhost:9090.

> **Note:** `mtp_pc_src/` in this repository is a **snapshot** of the PC
> coordinator source tree at `C:\llama.cpp-mtp` (commit `20a04b2`, tag `b9886`).
> It exists so a person reading the repo remote can see what the PC tree looked
> like, including the one local patch in `src/llama-model-loader.cpp`. The live
> build happens from `C:\llama.cpp-mtp` on the Master PC, not from this snapshot.

## License

See [LICENSE](LICENSE) (MIT). Adjust the copyright holder to taste.
