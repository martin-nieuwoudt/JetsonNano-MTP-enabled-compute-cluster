# Agent Swarm Deployment — Actual Implementation

This documents the **real** cloud swarm launcher that lives in this `Cluster` folder.
It is a PowerShell harness that fans out OpenRouter models as parallel agents on any
problem. It is NOT a Docker/Kubernetes/C++ service (that earlier draft was fabricated
and has been discarded).

---

## What it is

A **cloud swarm**: you (via the orchestrator Copilot in chat, or the VS Code Task menu)
name a problem brief and a list of OpenRouter models. The harness runs every
`(model × target)` pair as its own parallel agent job and collects the results.

Two modes:
- **Consultation** — no files; each named model answers the brief (problem text).
- **File patch** — pulls a file (local, or remote via scp), sends it + brief to each
  model, writes the patched result back.

---

## Files in this folder (`swarm/`)

This folder is **self-contained and portable** — copy it anywhere and it works
there. All paths resolve relative to the script's own location (`$PSScriptRoot`),
so nothing hard-codes `C:\Users\marti\Desktop\Cluster`.

| File | Purpose |
|------|---------|
| `swarm_launch.ps1` | General launcher. Params: `-Brief`, `-Models`, `-Targets`, `-Remote`, `-MaxRetry`, `-Timeout`. |
| `swarm_or_agent.ps1` | Single-file convenience wrapper (one model, one target). |
| `briefs/` | Problem briefs (e.g. `cuda_cpp17_to_cpp14.md`, `test_problem.md`). Add your own. |
| `_work/` | Outputs — each model's answer, named by model slug. |
| `.vscode/tasks.json` | Prebuilt VS Code tasks (run via Command Palette → Tasks: Run Task). |
| `or_key_ui.ps1` | Windows Forms GUI to enter the OpenRouter API key (writes to User env + `.openrouter.json`). |
| `swarm.code-workspace` | Open this to load the swarm folder + tasks in one click. |

---

## How to use it

### From chat (orchestrator runs this)
```
# Consultation (any problem, you name the models):
.\swarm_launch.ps1 -Brief briefs/<your-brief>.md -Models "modelA","modelB"

# File patch (remote file on node0):
.\swarm_launch.ps1 -Brief briefs/cuda_cpp17_to_cpp14.md `
    -Models "nvidia/nemotron-3-super-120b-a12b:free","tencent/hy3:free" `
    -Targets /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/common.cuh `
    -Remote jetson@192.168.50.150
```

### From VS Code (no terminal)
1. Open `swarm.code-workspace` (or the `swarm` folder).
2. Command Palette → `Tasks: Run Task` → pick a task:
   - **Swarm: Enter OpenRouter API Key (GUI)** — set key once (persists in User env).
   - **Swarm: CUDA C++17→C++14 (common.cuh)**
   - **Swarm: CUDA C++17→C++14 (all MTP shards)**
   - **Swarm: Consult (test_problem, 2 models)**

---

## Prerequisites (one-time)
- `OPENROUTER_API_KEY` in your **User** environment (the GUI task writes it there).
- WSL `Ubuntu` distro (only needed for remote `-Remote` scp pulls/pushes).
- SSH key to node0 (`jetson@192.168.50.150`) already authorized.

---

## Adding a new problem
1. Drop a brief at `briefs/<name>.md` (instructions for the models).
2. Tell the orchestrator: *"deploy a swarm on `<name>` with models A, B, C."*
3. The orchestrator runs `swarm_launch.ps1`; results land in `_work/`.

---

## Notes / gotchas
- Free-model IDs rotate on OpenRouter. If a model returns `400 not a valid model ID`,
  re-query `https://openrouter.ai/api/v1/models` and pick a current `:free` ID.
- Free models route through upstream providers and get **429 rate-limited**. The
  harness auto-retries with backoff (`-MaxRetry`, default 4).
- The Jetson cluster is only touched when you pass `-Remote jetson@192.168.50.150`.
  Consultation mode is pure cloud and needs no cluster.
- `api.openrouter.ai` sometimes fails DNS resolution right after a router cycle;
  `openrouter.ai` (the host the harness calls) is the one that must resolve.