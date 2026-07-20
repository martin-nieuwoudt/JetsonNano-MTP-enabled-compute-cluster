# Cluster Swarm Launcher

Deploy a **cloud swarm** of OpenRouter models on any problem, from VS Code or the terminal.
The orchestrator (GitHub Copilot in chat) runs `swarm_launch.ps1` on your command.

This folder (`swarm/`) is **self-contained and portable**: copy it anywhere and it
works there. All paths are resolved relative to the script's own location
(`$PSScriptRoot`), so nothing hard-codes `C:\Users\marti\Desktop\Cluster`.

## What it does
- Fans out **every (model × target) pair** as its own parallel agent job.
- Two modes:
  - **Consultation** — no files; each named model answers the brief (problem text).
  - **File patch** — pulls a file (local or remote via scp), sends it + brief to each model, writes the result back.
- Auto-retries on HTTP 429 (rate limit) with backoff.

## Files
- `swarm_launch.ps1` — the general launcher. Params: `-Brief`, `-Models`, `-Targets`, `-Remote`, `-MaxRetry`, `-Timeout`.
- `swarm_or_agent.ps1` — single-file convenience wrapper (one model, one target).
- `briefs/` — problem briefs. Add your own `.md` here.
- `_work/` — outputs (each model's answer, named by model slug).
- `.vscode/tasks.json` — prebuilt VS Code tasks (run via Command Palette → Tasks: Run Task).
- `swarm.code-workspace` — open this to load the swarm folder + tasks in one click.

## Usage (from chat, the orchestrator runs this for you)
```
# Consultation (any problem, you name the models):
.\swarm_launch.ps1 -Brief briefs/<your-brief>.md -Models "modelA","modelB"

# File patch (remote file on node0):
.\swarm_launch.ps1 -Brief briefs/cuda_cpp17_to_cpp14.md `
    -Models "nvidia/nemotron-3-super-120b-a12b:free","tencent/hy3:free" `
    -Targets /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/common.cuh `
    -Remote jetson@192.168.50.150
```

## Prereqs
- `OPENROUTER_API_KEY` set in your **User** environment (the `or_key_ui.ps1` GUI writes it there).
- WSL `Ubuntu` distro present (only needed for remote `-Remote` scp pulls/pushes).
- SSH key to node0 (`jetson@192.168.50.150`) already authorized.

## Adding a new problem
1. Drop a brief at `briefs/<name>.md` (instructions for the models).
2. Tell the orchestrator: "deploy a swarm on `<name>` with models A, B, C."
3. The orchestrator runs `swarm_launch.ps1` and reports results from `_work/`.
