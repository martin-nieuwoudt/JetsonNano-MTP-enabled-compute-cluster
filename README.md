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
| [`Nano Work Plan.md`](Nano%20Work%20Plan.md) | **Primary build manual.** Phase-by-phase from SD-card flash to live 11-node inference. Single source of truth for architecture and procedures. |
| [`MTP CUDA Enablement Work Plan.md`](MTP%20CUDA%20Enablement%20Work%20Plan.md) | The CUDA 10.2 / C++14 port of the MTP source tree that lets the Nano serve MTP models. |
| [`MTP_CUDA_STATUS.md`](MTP_CUDA_STATUS.md) | Live status & continuation doc for the MTP CUDA port. |
| [`Docs/`](Docs/) | Reference material, design notes, and status history. |

## Repository layout

```
code/                  Canonical orchestration scripts (dashboard, MCP server, deploy, QoS)
code/mcp/              FastMCP server (RPC + Tier1 + Tier2 + model registry + power) + single-source-of-truth config
code/methods/          Simulation-method library (Phase 1 research tooling)
Docs/                  Instruction + reference docs
MTP enablement files/  MTP CUDA port helpers, logs, and the 27 MTP-only file inventory
Nano Work Plan.md      ← the bible
```

## Quick start

1. Read [`Nano Work Plan.md`](Nano%20Work%20Plan.md) end-to-end. It defines
   `CLUSTER_ROOT` (your working copy of this repo) and every changeable fact
   (node IPs, ports, model registry) lives in `code/mcp/cluster_config.py`.
2. Flash + bootstrap the nodes per Phases 1–9.
3. Build the MTP CUDA worker (see `MTP CUDA Enablement Work Plan.md`).
4. Launch the dashboard:
   ```
   C:\Python314\pythonw.exe code\cluster_telemetry.py web
   ```
   then open http://localhost:9090.

## The MTP PC build tree is a submodule

`mtp_pc_src/` is a **separate upstream llama.cpp fork** and is tracked as a git
submodule, not committed inline. After creating a GitHub remote for the fork,
wire it up with:

```powershell
git submodule add <your-fork-url> mtp_pc_src
```

Until then it is excluded via `.gitignore`.

## License

See [LICENSE](LICENSE) (MIT). Adjust the copyright holder to taste.
