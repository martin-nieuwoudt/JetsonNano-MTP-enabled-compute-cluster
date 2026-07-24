"""
cluster_config.py — SINGLE SOURCE OF TRUTH for the Jetson Nano 11-node cluster.

Every changeable fact about the cluster lives here and ONLY here:
  - node IPs / names
  - RPC port (llama.cpp) and PyCUDA worker ports (GEMM / embedding / ring)
  - shard counts, topology, throttling limits
  - model registry (local GGUF paths + HF download URLs)
  - SSH identity used by the PC orchestrator to reach the nodes

Tool code MUST read from this module; it must never hardcode node lists, ports,
or model paths. This satisfies the architectural invariant: "Changeable logic is
never hardcoded."
"""

from __future__ import annotations

import os
import json

# ---------------------------------------------------------------------------
# NODES  (node0 = 192.168.50.150 is the golden clone template / GUI kept)
# ---------------------------------------------------------------------------
NODE_IPS = [f"192.168.50.{i}" for i in range(150, 161)]          # 150..160
NODE_NAMES = [f"nano{i:02d}" for i in range(11)]                 # nano00..nano10
# Fixed private-LAN address of the golden node0 template. This is a static
# cluster topology constant on a trusted LAN, not user-supplied input.
# nosec B104: hardcoded IP is intentional and safe here.
NODE0_IP = "192.168.50.150"  # NOSONAR
SHARD_COUNT = len(NODE_IPS)                                      # 11

# ---------------------------------------------------------------------------
# PORTS  (must never collide — RPC stays on 50052)
# ---------------------------------------------------------------------------
RPC_PORT = 50052            # llama.cpp ggml-rpc-server (dense 70B layer-piping)
GEMM_PORT = 9999            # Tier 1: star-topology FP16 matrix self-mul worker
EMBED_PORT = 9998           # Tier 1: token-id -> float16 embedding projection worker
RING_PORT = 8888            # Tier 2: MoE expert-parallel ring worker
RING_HIDDEN_DIM = 4096      # ring hidden-state width (MUST match HIDDEN_DIM in jetson_ring_worker.py)
RING_BATCH_SIZE = 16        # ring micro-batch (MUST match BATCH_SIZE in jetson_ring_worker.py)
RING_SEQUENCE_LEN = 512     # ring sequence length (MUST match SEQUENCE_LEN in jetson_ring_worker.py)

# ---------------------------------------------------------------------------
# TOPOLOGY / THROTTLING
# ---------------------------------------------------------------------------
TOPOLOGY = "star"                       # GEMM + embedding use star; ring overrides per-job
MAX_CONCURRENT_NET_STREAMS = 4          # switch-buffer protection (asyncio.Semaphore)
EMBEDDING_DIM = 768                     # embedding worker projection width
VOCAB_SIZE = 50000                      # mock embedding weight matrix vocab size

# ---------------------------------------------------------------------------
# SMALL-MODEL INSTRUCTION PATH  (Phase 11 — dual-mode, single source of truth)
# The small LLMs (Gemma 4 E4B, Phi-3, Qwythos-9B, ...) receive TEXT instructions
# via the orchestrator. ALONGSIDE the text, the orchestrator can attach a float16
# embedding of the instruction (produced by the 9998 embedding tier) as a
# structured FP16 companion payload. This is the "instructions in FP16" option:
#   - TEXT path      : input_data (always present — LLMs need text)
#   - FP16 companion : fp16_instruction_b64 + fp16_tokens (optional, when the
#                      embedding tier is live). Both travel together on a task.
# Changeable facts about the FP16 path live here, not in the worker/agent code.
# ---------------------------------------------------------------------------
FP16_INSTRUCTION_ENABLED = True         # attach float16 embedding to tasks when live
FP16_EMBED_PORT = EMBED_PORT            # 9998 — the tier that produces the FP16 vector

# ---------------------------------------------------------------------------
# SSH  (PC -> node, used by deploy / worker-launch / health tools)
# ---------------------------------------------------------------------------
SSH_USER = "jetson"
SSH_KEY_PATH = r"C:\Users\marti\.ssh\id_ed25519"
SSH_OPTS = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null"]

# ---------------------------------------------------------------------------
# PATHS  (PC-side)
# ---------------------------------------------------------------------------
CODE_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.dirname(CODE_DIR)
MODELS_DIR = r"C:\Models"
OUTPUTS_DIR = r"C:\Outputs"
LLAMA_CLI = r"C:\llama.cpp\build\bin\llama-cli.exe"
# MTP-capable CLI (same build as the node ggml-rpc-server, commit 20a04b2).
# The dashboard's single-mode chat uses THIS binary + all-11-RPC-workers, which
# is the exact path the proven CLI inference test uses. Do NOT point the
# dashboard at SERVER_BIN (llama-server.exe) — that is a different component
# and was the source of the 503 / WinError 10054 out-of-sync errors.
MTP_CLI = r"C:\llama.cpp-mtp\build\bin\llama-cli.exe"
RPC_METRICS_FILE = os.path.join(CODE_DIR, "rpc_metrics.json")
# Canonical metrics file (single source of truth). The dashboard's
# fetch_inference_telemetry() reads this; the chat endpoint writes it.
METRICS_FILE = RPC_METRICS_FILE

# ---------------------------------------------------------------------------
# PERSISTENT INFERENCE SERVER  (single source of truth)
# cluster_infer.py re-uploads the whole model across the 11 nanos on EVERY
# prompt (wasteful for big GGUFs). llama-server loads the sharded model ONCE
# and keeps it RESIDENT in the nanos' UMA RAM, serving unlimited prompts over
# HTTP. The shards stay put until the server is manually `stop`ped. Changeable
# facts about the server live here ONLY; never hardcode in scripts.
# ---------------------------------------------------------------------------
# MTP build matches the node ggml-rpc-server (commit 20a04b2) deployed fleet-wide.
# RPC is lockstep: the llama-server client MUST be the same build as the node
# daemon, or model load fails with "server did not come up" / "no model resident".
SERVER_BIN = r"C:\Installers\System\llama-b10092-bin-win-cuda-12.4-x64\llama-server.exe"
SERVER_HOST = "192.168.50.202"
SERVER_PORT = 8080
SERVER_PID_FILE = os.path.join(CODE_DIR, "cluster_server.pid")
SERVER_LOG = os.path.join(CODE_DIR, "cluster_server.log")
# daemon, or model load fails with "server did not come up" / "no model resident".
SERVER_BIN = r"C:\llama.cpp-mtp\build\bin\llama-server.exe"
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8080
SERVER_PID_FILE = os.path.join(CODE_DIR, "cluster_server.pid")
SERVER_LOG = os.path.join(CODE_DIR, "cluster_server.log")
# Chat-box file uploads land here (single source of truth). The dashboard's
# /api/chat/upload endpoint writes user-attached files for use as prompt context.
CHAT_UPLOAD_DIR = os.path.join(WORKSPACE, "chat_uploads")

# ---------------------------------------------------------------------------
# EXTERNAL SETTINGS  (single source of truth — deterministic workflow)
# All generation-time tunables (sampling, context size, output length) live in
# cluster_settings.json, loaded below. The Jetson nodes are compute-only
# (ggml-rpc-server) and never sample or parse these; everything happens on the
# PC coordinator. The JSON OVERRIDES the built-in defaults below — if the file
# is missing or invalid, we fall back to these literals so the system never
# crashes. Change tunables in the JSON, never in the launch scripts.
# ---------------------------------------------------------------------------
# Built-in fallback defaults (used only if cluster_settings.json is absent/bad).
_SETTINGS_FALLBACK = {
    "sampling": {"temp": 0.1, "min_p": 0.05, "top_p": 0.9, "repeat_penalty": 1.1},
    "context":  {"ctx_size": 16384},
    "output":   {"max_tokens": 4096},
    # This is a BATCH cluster: jobs are queued and left to run as long as they
    # need. request_timeout is the per-HTTP-call ceiling for generation. null =
    # no timeout (let long batch jobs finish). Set a number of seconds only if
    # you want a hard wall-clock guard on a single completion call.
    "runtime":  {"request_timeout": None},
}


def _read_json_file(path):
    """Read and parse a JSON file, returning {} on any failure."""
    import json as _json
    try:
        with open(path, "r", encoding="utf-8") as _fh:
            return _json.load(_fh) or {}
    except Exception:
        return {}


def _coerce_value(raw_value, default_value):
    """Coerce raw_value to the type of default_value, or return default on failure.

    A default_value of None means 'no limit' — accept a number or None only.
    """
    if default_value is None:
        # None means "no limit" (e.g. request_timeout). Accept a number
        # or null; anything else falls back to None.
        return raw_value if isinstance(raw_value, (int, float)) and not isinstance(raw_value, bool) else None
    try:
        return type(default_value)(raw_value)
    except (TypeError, ValueError):
        return default_value


def _clamp_settings_bounds(merged):
    """Clamp merged settings to safe runtime bounds (mutates in-place)."""
    merged["context"]["ctx_size"] = max(512, int(merged["context"]["ctx_size"]))
    merged["output"]["max_tokens"] = max(1, int(merged["output"]["max_tokens"]))
    for _k in ("temp", "min_p", "top_p", "repeat_penalty"):
        merged["sampling"][_k] = float(merged["sampling"][_k])


def _load_settings():
    """Load cluster_settings.json as an override layer over _SETTINGS_FALLBACK.

    Stability-first: any missing/invalid field falls back to the built-in
    default. A missing or corrupt file is NOT fatal — we run on defaults.
    Values are clamped to sane bounds so a typo cannot break the runtime.
    """
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "cluster_settings.json")
    data = _read_json_file(path)
    merged = {}
    for _section, _defaults in _SETTINGS_FALLBACK.items():
        _raw = data.get(_section, {}) or {}
        _out = {}
        for _k, _def in _defaults.items():
            _out[_k] = _coerce_value(_raw.get(_k, _def), _def)
        merged[_section] = _out
    _clamp_settings_bounds(merged)
    return merged


SETTINGS = _load_settings()

# Effective tunables (single source of truth, resolved from JSON-or-fallback).
SAMPLING_TEMP = SETTINGS["sampling"]["temp"]
SAMPLING_MIN_P = SETTINGS["sampling"]["min_p"]
SAMPLING_TOP_P = SETTINGS["sampling"]["top_p"]
SAMPLING_REPEAT_PENALTY = SETTINGS["sampling"]["repeat_penalty"]
CTX_SIZE_DEFAULT = SETTINGS["context"]["ctx_size"]
MAX_TOKENS_DEFAULT = SETTINGS["output"]["max_tokens"]
REQUEST_TIMEOUT = SETTINGS["runtime"]["request_timeout"]   # None = no limit

def reload_settings():
    """Re-read cluster_settings.json and update all global tunables.

    Call this before returning settings from API endpoints so the
    dashboard always sees the latest saved values, not stale cached ones.
    """
    global SETTINGS, SAMPLING_TEMP, SAMPLING_MIN_P, SAMPLING_TOP_P
    global SAMPLING_REPEAT_PENALTY, CTX_SIZE_DEFAULT, MAX_TOKENS_DEFAULT
    global REQUEST_TIMEOUT

    SETTINGS = _load_settings()
    SAMPLING_TEMP = SETTINGS["sampling"]["temp"]
    SAMPLING_MIN_P = SETTINGS["sampling"]["min_p"]
    SAMPLING_TOP_P = SETTINGS["sampling"]["top_p"]
    SAMPLING_REPEAT_PENALTY = SETTINGS["sampling"]["repeat_penalty"]
    CTX_SIZE_DEFAULT = SETTINGS["context"]["ctx_size"]
    MAX_TOKENS_DEFAULT = SETTINGS["output"]["max_tokens"]
    REQUEST_TIMEOUT = SETTINGS["runtime"]["request_timeout"]

# ---------------------------------------------------------------------------
# MODEL STORAGE ARCHITECTURE  (RETIRED 2026-07-15 — single source of truth)
# The node0 USB SSD (/mnt/ssd/models, NFS-exported) was REMOVED and reformatted
# as a local PC drive (D:). The Jetson nodes are dumb weight *receivers*: the PC
# reads the GGUF from C:\Models (MODELS_DIR) and PUSHES every shard over RPC on
# each run. Nodes NEVER load from disk, so there is no on-node model store and no
# NFS mount. These constants are retained ONLY for backward-compat with legacy
# sync/prewarm scripts (now dead); the authoritative model location is MODELS_DIR.
# ---------------------------------------------------------------------------
MODEL_NODE_IP = NODE0_IP                       # RETIRED as model store (was Nano Zero)
MODEL_DIR_ON_NODE0 = "/mnt/ssd/models"        # RETIRED 2026-07-15 — SSD removed
MODEL_MOUNT_ON_WORKER = "/mnt/nano-ssd"       # RETIRED 2026-07-15 — NFS mount gone

# ---------------------------------------------------------------------------
# TOKENIZER MODELS  (Phase 11 — single source of truth for the FP16 path)
# The FP16 instruction path tokenizes text with the REAL model vocab via
# llama-tokenize.exe (pinned build) reading each model's GGUF. Map a registry
# model key -> its GGUF path here. `_fallbacks` lists small GGUFs that share a
# tokenizer family with bigger models the pinned binary cannot load (e.g.
# qwen35-arch Qwythos-9B uses the tiny-qwen tokenizer). If a model_key is not
# listed or its GGUF is missing, embed_client falls back to a deterministic
# mock so the FP16 path never hard-fails.
# ---------------------------------------------------------------------------
TOKENIZER_MODELS = {
    "phi-3-mini-4k-instruct-q6_k": os.path.join(MODELS_DIR, "Phi-3-mini-4k-instruct-Q6_K.gguf"),
    "codestral-22b-q8_0": os.path.join(MODELS_DIR, "Codestral-22B-v0.1-Q8_0.gguf"),
    "qwen2.5-72b-iq3_m": os.path.join(MODELS_DIR, "Qwen2.5-72B-Instruct-IQ3_M.gguf"),
    # qwythos-9b is qwen35-arch; the pinned binary can't load it, so we use the
    # tiny-qwen GGUF (same Qwen tokenizer family) as the tokenizer source.
    "qwythos-9b-q8_0": os.path.join(MODELS_DIR, "tiny_test", "qwen0.5b-q4km.gguf"),
    "_fallbacks": [
        os.path.join(MODELS_DIR, "tiny_test", "qwen0.5b-q4km.gguf"),
    ],
}

# ---------------------------------------------------------------------------
# REMOTE METHOD HARNESS DIR  (Track 3 — Anti-Dark Forest simulation tools)
# The pure-numpy method harnesses (../methods/: marl, montecarlo, thermo_ca,
# kl_div, lean, bayesian) are pushed to this path on every node so a small-model
# agent can run them locally (compute stays on-node, comms stay light).
# ---------------------------------------------------------------------------
REMOTE_METHODS_DIR = "/home/jetson/methods"

# ---------------------------------------------------------------------------
# SHARED SSD  (Nano Zero's USB SSD — model store + cluster scratch)
# Single source of truth for WHERE the SSD lives and how telemetry probes it.
# ---------------------------------------------------------------------------
SSD_NODE_IP = NODE0_IP                          # SSD is physically plugged into Nano Zero
SSD_MOUNT = "/mnt/ssd"                          # mount point on node0 (ext4 on /dev/sda1)
SSD_SHARE = "ssd"                               # Samba share name exported from node0
SSD_DEVICE_HINT = "/dev/sda1"                   # expected block device (verified at runtime)

# ---------------------------------------------------------------------------
# RPC DAEMON MEMORY BUFFERS  (Phase 7 — MANDATORY per-node -m)
# Jetson is UMA (no discrete VRAM). Without -m, rpc-server reports ~14 MB and
# gets almost no layers. node0 keeps the GUI so gets a SMALLER buffer.
# ---------------------------------------------------------------------------
RPC_DAEMON_M_NODE0 = 3000                     # Nano Zero (GUI kept)
RPC_DAEMON_M_WORKER = 3600                     # headless workers

# ---------------------------------------------------------------------------
# RPC DAEMON BINARY / LAUNCH  (Phase 7 — single source of truth)
# mlockall_wrapper is a setuid-root helper: it calls mlockall() then execv's
# ./rpc-server (binary name at b56f079e2). The wrapper hardcodes the binary
# name, so launch commands must NOT pass ./rpc-server as an extra argument.
# ---------------------------------------------------------------------------
RPC_BINARY = "rpc-server"                       # binary name at pinned commit b56f079e2
RPC_BIN_DIR = "/home/jetson/llama.cpp/build/bin"  # rpc-server + mlockall_wrapper live here
MLOCK_WRAPPER = "mlockall_wrapper"               # setuid helper: mlockall() then execv rpc-server

# ---------------------------------------------------------------------------
# BUILD VARIANTS  (dual-build: stable default + selectable MTP secondary)
# MTP (multi-token prediction) models need a newer llama.cpp than the pinned
# stable commit. We keep BOTH builds side by side and select per-run so the
# stable build stays the default and nothing regresses. The node rpc-server
# MUST match the client build (RPC is collective/lockstep), so switching build
# also switches the node daemon. Single source of truth -- never hardcode paths.
# ---------------------------------------------------------------------------
BUILD_VARIANTS = {
    "stable": {
        "label": "pinned stable (b56f079e2, 2025-01-04)",
        "commit": "b56f079e2",
        "cli": r"C:\llama.cpp\build\bin\llama-cli.exe",
        "rpc_bin_dir": "/home/jetson/llama.cpp/build/bin",
        "rpc_binary": "rpc-server",
    },
    "mtp": {
        "label": "MTP-capable (multi-token prediction), release b9886 (2026-07-06)",
        "commit": "b9886",   # first stable release tag with qwen3.5 (Qwythos) + MTP draft heads
        "cli": r"C:\llama.cpp-mtp\build\bin\llama-cli.exe",
        "rpc_bin_dir": "/home/jetson/llama.cpp-mtp/build/bin",
        "rpc_binary": "ggml-rpc-server",   # b9886 names it ggml-rpc-server (rpc-server alias added later)
    },
}
DEFAULT_BUILD = "stable"

# ---------------------------------------------------------------------------
# CLIENT TENSOR SPLIT  (Phase 10 — handles node0's lower headroom)
# 11 values map 1:1 to --rpc servers in order (node0 first). Overrides the
# free-memory probe so node0 (GUI kept) is not OOMed. Keep this OR per-node -m,
# not neither. We keep BOTH: -m guarantees real memory reporting, this caps
# node0's layer share.
# ---------------------------------------------------------------------------
TENSOR_SPLIT_DEFAULT = "1,1,1,1,1,1,1,1,1,1,1"

# ---------------------------------------------------------------------------
# ENSEMBLE FOUNDATION  (size-based split + random node selection)
# A model is pushed onto the MINIMUM node count that fits it (small models must
# not be fanned across all 11 nodes — that pays 11 RPC round-trips per decode
# step for zero capacity gain). Node selection is RANDOM each run so the same
# model mix never hammers the same nodes twice (electronic/thermal wear spread).
# node0 IS included (excluding wastes 1/11 of the fleet) but gets a smaller
# tensor-split share because it keeps the GUI. Single source of truth.
# ---------------------------------------------------------------------------
# Size-based split guideline: (max_model_bytes, node_count) tiers, evaluated in
# order. A model whose size is <= the tier's max uses that many nodes (equal
# split within the subset). Anything larger than the last tier uses all
# SHARD_COUNT nodes (legacy behaviour).
# Per-node CUDA buffer ceiling. The Jetson Nano has NO discrete VRAM — the
# Tegra X1 shares 4 GB LPDDR4 (UMA) and the CUDA carve-out tops out at ~2.5 GB
# of usable device buffers. A shard larger than this fails to allocate on the
# node and the RPC server returns ggml-rpc.cpp:488 (malformed/crashed). The node
# count for a model MUST be derived from this ceiling, not a fixed size table,
# or big models pick too few nodes and every shard overflows.
PER_NODE_CUDA_CEILING_BYTES = int(1.8 * 1024**3)   # ~1.8 GB safe headroom
# UMA anon-rss overhead on top of the raw shard (weights + KV + activations).
SHARD_OVERHEAD_FRAC = 0.35

# Size->count table. The Jetson Nano nodes accept shards up to ~3 GB, so a
# 9.5 GB model lands on 4 nodes (~2.4 GB shard each) and fits comfortably.
SPLIT_GUIDELINE = [
    (3   * 1024**3, 1),    # <= 3 GB   -> 1 node
    (6   * 1024**3, 2),    # <= 6 GB   -> 2 nodes
    (12  * 1024**3, 4),    # <= 12 GB  -> 4 nodes
    (24  * 1024**3, 8),    # <= 24 GB  -> 8 nodes
    # else -> SHARD_COUNT (11)
]
RANDOM_NODE_SELECTION = True        # pick subset nodes at random each run
EXCLUDE_NODE0_FROM_RANDOM = False   # node0 IS included — excluding wastes 1/11 of the fleet
# node0 (.150) keeps the GUI, so it has LESS free RAM than the headless
# workers (RPC_DAEMON_M_NODE0=3000 vs RPC_DAEMON_M_WORKER=3600). Giving it a
# full share makes its worker OOM at RPC_CMD_SET_TENSOR ("recv failed" /
# "Remote RPC server crashed") and the llama-server exits -> dashboard 503.
# Keep it smaller than the workers so its shard fits its reduced memory.
NODE0_SPLIT_WEIGHT = 0.5            # node0 keeps the GUI -> less headroom -> smaller share
NODE_SELECTION_SEED = None          # None = fresh random each call; int = reproducible (debug)

# ---------------------------------------------------------------------------
# ENSEMBLE CONCURRENCY  (builds on the foundation above)
# Each model in an ensemble gets its own detached llama-server on the PC, on a
# disjoint random node subset. The port pool starts at 8081 so it NEVER collides
# with the single-model chat server on SERVER_PORT (8080). 11 slots = the
# hardware ceiling for <3GB models (one per node). The real concurrency limiter
# is the node budget (partition_ensemble), not this pool.
# ---------------------------------------------------------------------------
SERVER_PORT_POOL = [8081, 8082, 8083, 8084, 8085, 8086, 8087, 8088, 8089, 8090, 8091]   # [8081..8091]
ENSEMBLE_AUTO_STOP = False       # KEEP RESIDENT after a run (instant follow-ups > freed RAM)
ENSEMBLE_RANDOM_N = 3            # default subset size for the random-subset mode
ENSEMBLE_MAX_MODELS = SHARD_COUNT  # cap at 11 (one per node); partition_enforce enforces real budget
# Ensemble-start ejects the single-model resident first so partition_ensemble
# always has free nodes (the resident holds all 11).
ENSEMBLE_EJECT_RESIDENT_FIRST = True
# The dashboard System Prompt box applies to ALL ensemble models (consistent
# mandate so models are judged against the same rules).
ENSEMBLE_APPLY_SYSTEM_PROMPT = True

# ---------------------------------------------------------------------------
# ANTI-INCAST PACING  (Phase 12 — single source of truth)
# ROOT CAUSE OF 2026-07-14 INSTABILITY: the llama.cpp RPC client opens all 11
# node connections SIMULTANEOUSLY and blasts each node's weight shard at once.
# That incast burst overwhelms the small interconnect switch -> packet drops ->
# TCP resets -> nodes log "recv failed (bytes_recv=0)" -> reconnect loop (the
# "storm" that made the dashboard report "RPCs down" while daemons stayed alive).
# FIX (two layers, both mandatory and boot-persistent):
#   (A) NODE-SIDE EGRESS SHAPER  — `tc` caps the RPC upload burst per node so a
#       single node can never flood the switch. Installed as a systemd oneshot
#       (llama-rpc-shape.service) that runs BEFORE llama-rpc.service on boot.
#   (B) CLIENT-SIDE STAGED CONNECT — cluster_infer.py brings nodes online a few
#       at a time (STAGE_NODES_AT_ONCE) with a settle delay (STAGE_SETTLE_S) so
#       the weight-upload burst is spread out instead of simultaneous.
# Changeable facts live here ONLY; never hardcode in scripts.
# ---------------------------------------------------------------------------
RPC_SHAPER_ENABLED = True          # install + apply the tc egress limiter
RPC_SHAPER_IFACE = "eth0"          # real ethernet iface on every Nano
RPC_SHAPER_RATE = "850mbit"        # per-node egress cap (switch is 1G; leave headroom)
RPC_SHAPER_BURST = "64kb"          # small burst bucket -> smooths incast spikes
RPC_SHAPER_PORT = RPC_PORT          # shape only the RPC port (50052)
STAGE_NODES_AT_ONCE = 3            # client connects this many nodes per stage
STAGE_SETTLE_S = 4.0              # seconds to wait between stages (let burst drain)
# Weakest-node OOM guard: refuse to launch if a model's per-node shard estimate
# (model_bytes / SHARD_COUNT, +35% UMA overhead) exceeds this fraction of the
# weakest node's MemAvailable. node160 ~3.47 GB today; 0.80 = ~2.78 GB ceiling.
OOM_GUARD_WEAKEST_HEADROOM_FRAC = 0.80
OOM_GUARD_OVERHEAD_FRAC = 0.35     # UMA anon-rss overhead on top of raw shard

# ---------------------------------------------------------------------------
# CLUSTER STATE  (single source of truth for the watchdog <-> power flag)
# The dashboard "OS Shutdown" button and the fault-tolerant watchdog share ONE
# flag so they never fight: when an OS shutdown is in progress, the watchdog
# stands down (does NOT re-slice or re-admit nodes). Physical POWER (5V cut) is
# handled separately by a Sonoff switch via Alexa and is OUT OF SCOPE for
# software — these two concerns must stay distinct (see Work Plan Phase 15).
# ---------------------------------------------------------------------------
CLUSTER_STATE_FILE = os.path.join(CODE_DIR, "cluster_state.json")
CLUSTER_MODE_NORMAL = "normal"
CLUSTER_MODE_MAINTENANCE = "maintenance"


def get_cluster_mode() -> str:
    """Return the current cluster mode: 'normal' or 'maintenance'."""
    try:
        with open(CLUSTER_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("mode", CLUSTER_MODE_NORMAL)
    except Exception:
        return CLUSTER_MODE_NORMAL


def set_cluster_mode(mode: str) -> None:
    """Persist the cluster mode. mode must be 'normal' or 'maintenance'."""
    import datetime
    data = {"mode": mode, "ts": datetime.datetime.now().isoformat(timespec="seconds")}
    try:
        with open(CLUSTER_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

# ---------------------------------------------------------------------------
# GOLDEN-PROMPT DETERMINISM CHECK  (QoS #3 — whole-cluster, not per-node)
# RPC is collective, so there is no per-node answer to hash. This asserts the
# whole cluster produces the same output for a fixed prompt (catches weight/
# model corruption that changes results).
# ---------------------------------------------------------------------------
GOLDEN_PROMPT = "The chemical symbol for water is"
GOLDEN_TOKENS = 24

# ---------------------------------------------------------------------------
# MODEL REGISTRY
# One authoritative place for every model the cluster can run.
#   local   = path on this PC (orchestrator)
#   hf_url  = direct HuggingFace resolve URL (for resumable download)
#   kind    = "dense" | "moe"
#   fits_pc = True if it fits the ~35GB PC headroom WITHOUT node sharding
#   notes   = short rationale
# ---------------------------------------------------------------------------
MODELS = {
    "llama-3.3-70b-iq3_xs": {
        "local": os.path.join(MODELS_DIR, "Llama-3.3-70B-Instruct-IQ3_XS.gguf"),
        "hf_url": "https://huggingface.co/bartowski/Llama-3.3-70B-Instruct-GGUF/resolve/main/Llama-3.3-70B-Instruct-IQ3_XS.gguf",
        "kind": "dense", "fits_pc": False,
        "notes": "Drop-in 70B dense replacement. Runs via llama.cpp RPC layer-piping across 11 nodes.",
    },
    "qwen2.5-72b-iq3_m": {
        "local": os.path.join(MODELS_DIR, "Qwen2.5-72B-Instruct-IQ3_M.gguf"),
        "hf_url": "https://huggingface.co/bartowski/Qwen2.5-72B-Instruct-GGUF/resolve/main/Qwen2.5-72B-Instruct-IQ3_M.gguf",
        "kind": "dense", "fits_pc": False,
        "notes": "72B dense, world-class coding/JSON/multilingual. RPC layer-piping.",
    },
    "codestral-22b-q8_0": {
        "local": os.path.join(MODELS_DIR, "Codestral-22B-v0.1-Q8_0.gguf"),
        "hf_url": "https://huggingface.co/bartowski/Codestral-22B-v0.1-GGUF/resolve/main/Codestral-22B-v0.1-Q8_0.gguf",
        "kind": "dense", "fits_pc": True,
        "notes": "22B dense code specialist. Q8_0 ~23.6GB fits PC directly; sharding optional/accelerating.",
    },
    "deepseek-coder-v2-lite-q4_k_m": {
        "local": os.path.join(MODELS_DIR, "DeepSeek-Coder-V2-Lite-Q4_K_M.gguf"),
        "hf_url": "https://huggingface.co/bartowski/DeepSeek-Coder-V2-Lite-GGUF/resolve/main/DeepSeek-Coder-V2-Lite-Q4_K_M.gguf",
        "kind": "moe", "fits_pc": True,
        "notes": "16B total / 2.4B active MoE. Tier 2 ring target: 64 experts split ~6/node across Jetsons.",
    },
    "deepseek-r1-distill-qwen-32b-q6_k_l": {
        "local": os.path.join(MODELS_DIR, "DeepSeek-R1-Distill-Qwen-32B-Q6_K_L.gguf"),
        "hf_url": "https://huggingface.co/bartowski/DeepSeek-R1-Distill-Qwen-32B-GGUF/resolve/main/DeepSeek-R1-Distill-Qwen-32B-Q6_K_L.gguf",
        "kind": "dense", "fits_pc": True,
        "notes": "32B R1-distill reasoning model. Q6_K_L ~27.3GB fits PC directly; sharding optional/accelerating.",
    },
    "phi-3-mini-4k-instruct-q6_k": {
        "local": os.path.join(MODELS_DIR, "Phi-3-mini-4k-instruct-Q6_K.gguf"),
        "hf_url": "https://huggingface.co/bartowski/Phi-3-mini-4k-instruct-GGUF/resolve/main/Phi-3-mini-4k-instruct-Q6_K.gguf",
        "kind": "dense", "fits_pc": True,
        "notes": "3.8B small reasoner. Q6_K ~3.14GB, edge agentic node target.",
    },
    "qwythos-9b-q8_0": {
        "local": os.path.join(MODELS_DIR, "Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf"),
        "hf_url": "https://huggingface.co/empero-ai/Qwythos-9B-Claude-Mythos-5-1M-GGUF/resolve/main/Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf",
        "kind": "dense", "fits_pc": True,
        "requires_build": "mtp",   # MTP draft heads need the mtp build variant
        "notes": "9B Claude-Mythos fine-tune (MTP). Q8_0 ~9.79GB fits PC directly.",
    },
}

# ---------------------------------------------------------------------------
# HEALTH / TELEMETRY THRESHOLDS  (shared by telemetry + watchdog + QoS)
# ---------------------------------------------------------------------------
MIN_REQUIRED_RAM_GB = 3.0             # per-node floor for 70B IQ3_XS shards (UMA RAM)
                                    # Jetson Nano = 4GB LPDDR4; headless idle MemAvailable
                                    # is ~3.4-3.6GB. 3.0 leaves headroom and avoids
                                    # false-negative FAIL on a healthy node.
TOTAL_RAM_GATE_GB = 28.0              # cluster must expose >= this to pass audit (UMA RAM)
THERMAL_WARN_C = 80.0                 # Jetson begins throttling near 85C; warn early
THERMAL_FAIL_C = 85.0                 # hard throttle / shutdown-risk threshold
THERMAL_REJOIN_C = 70.0               # dropped node only rejoins once cooled below this
# Thermal zones reported by `tegrastats` that are NOT the compute silicon and
# must be excluded from the "hottest zone" reading. PMIC is the power-management
# IC (voltage regulator) -- it sits at a constant ~50C on every Nano regardless
# of load, so a naive max() over all zones always reports 50C and masks the real
# CPU/GPU/AO/thermal temps. Keep this list authoritative (single source of truth).
THERMAL_EXCLUDE_ZONES = ("PMIC",)
METRICS_FILE = os.path.join(WORKSPACE, "rpc_metrics.json")  # published by cluster_infer.py
WEB_HOST = "0.0.0.0"
WEB_PORT = 9090
MONVIEW_INTERVAL_SEC = 1.0
PROBE_INTERVAL_SEC = 5.0

# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def rpc_list() -> str:
    """Comma-separated 'ip:port' string for llama-cli --rpc."""
    return ",".join(f"{ip}:{RPC_PORT}" for ip in NODE_IPS)


def node_ip(index: int) -> str:
    return NODE_IPS[index]


def model_entry(key: str) -> dict:
    if key not in MODELS:
        raise KeyError(f"Unknown model '{key}'. Known: {', '.join(MODELS)}")
    return MODELS[key]


# ---------------------------------------------------------------------------
# ENSEMBLE HELPERS  (size-based split + random node selection + partition)
# These are the ONLY place node-subset logic lives. Scripts call them; they
# never recompute splits or pick nodes themselves.
# ---------------------------------------------------------------------------
import os as _os
from random import Random as _Random


def tier_for(model_path: str) -> int:
    """Return the node count a model needs, from SPLIT_GUIDELINE."""
    try:
        size = _os.path.getsize(model_path)
    except OSError:
        return SHARD_COUNT
    n = SHARD_COUNT
    for max_b, cnt in SPLIT_GUIDELINE:
        if size <= max_b:
            n = cnt
            break
    return n


def select_nodes_for_model(model_path: str):
    """Return (rpc_list, tensor_split) for the chosen subset of nodes.

    ALWAYS uses the full fleet (all SHARD_COUNT nodes): more nodes means
    smaller shards AND more parallel GPUs, which is strictly faster than a
    subset. node0 is included but gets NODE0_SPLIT_WEIGHT (smaller share, GUI
    kept). The --tensor-split length always equals the --rpc server count.
    """
    del model_path  # reserved for callers; fleet is always used
    chosen = list(NODE_IPS)                           # all 11 nodes
    split = ",".join(str(NODE0_SPLIT_WEIGHT) if ip == NODE0_IP else "1"
                     for ip in chosen)
    rpc = ",".join(f"{ip}:{RPC_PORT}" for ip in chosen)
    return rpc, split


def partition_ensemble(models):
    """Assign disjoint random node sets + ports to a list of model paths.

    Returns list of dicts: {model, port, rpc, split, nodes}.
    Biggest models pick first (they need the most nodes). Raises ValueError if
    the free-node budget cannot fit the set (no silent sharing — sharing would
    clobber shards). node0 is included in the pool.
    """
    remaining = list(NODE_IPS)                        # node0 INCLUDED
    rng = _Random(NODE_SELECTION_SEED)                # fixed-seed RNG for reproducible ensemble partitioning
    ports = list(SERVER_PORT_POOL)
    if len(models) > len(ports):
        raise ValueError(
            f"Too many models ({len(models)}) for port pool ({len(ports)}). "
            f"Max concurrent ensemble models = {len(ports)}.")
    # biggest first
    ordered = sorted(models, key=lambda m: _os.path.getsize(m), reverse=True)
    assignments = []
    for model in ordered:
        n = tier_for(model)
        if n > len(remaining):
            raise ValueError(
                f"Not enough free nodes for '{_os.path.basename(model)}' "
                f"(needs {n}, {len(remaining)} free). Reduce model count or sizes.")
        pick = rng.sample(remaining, n)
        remaining = [ip for ip in remaining if ip not in pick]
        split = ",".join(str(NODE0_SPLIT_WEIGHT) if ip == NODE0_IP else "1"
                         for ip in pick)
        assignments.append({
            "model": model,
            "port": ports.pop(0),
            "rpc": ",".join(f"{ip}:{RPC_PORT}" for ip in pick),
            "split": split,
            "nodes": list(pick),
        })
    return assignments
