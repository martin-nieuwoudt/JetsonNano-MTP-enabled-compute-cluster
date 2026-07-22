# JetsonNano MTP-enabled Compute Cluster

A software stack for a **star-topology compute cluster** built from a
Windows Master PC (CPU-only coordinator) and **11 NVIDIA Jetson Nano** worker
nodes interconnected over a **1 Gbps** Ethernet network.

The cluster supports two workload types:

| Workload | Mechanism | GPU side |
|---|---|---|
| LLM inference | **llama.cpp RPC** — master runs `llama-cli`, workers run `llama-rpc-server` | Jetson Nano (Maxwell GPU) |
| General GPU compute | **PyCUDA** — master serialises kernels + data, workers compile and execute them | Jetson Nano (UMA) |

All GPU computation runs on the Jetson Nano nodes, which exploit their
**Unified Memory Architecture (UMA)**: CPU and GPU share the same physical DRAM
pool, so host-to-device copies are zero-cost.

---

## Repository layout

```
.
├── shared/              # Shared protocol, configuration constants
│   ├── config.py        # Ports, timeouts, cluster constants
│   └── protocol.py      # Length-prefixed JSON wire protocol + socket helpers
│
├── master/              # Runs on the Windows Master PC
│   ├── coordinator.py   # Node registry, heartbeat watchdog, task routing
│   ├── llm_distributor.py   # Builds llama.cpp --rpc commands, runs inference
│   ├── pycuda_distributor.py  # Serialises PyCUDA workloads to workers
│   └── requirements.txt
│
├── worker/              # Runs on each Jetson Nano
│   ├── worker.py        # Main process: registration, heartbeat, task dispatch
│   ├── llm_rpc_server.py  # llama-rpc-server subprocess manager
│   ├── pycuda_worker.py   # Compiles and launches CUDA kernels
│   ├── uma_utils.py     # UMA memory allocation helpers (pinned, managed, zero-copy)
│   └── requirements.txt
│
├── config/
│   └── cluster.yaml     # IP addresses, ports, node IDs for all 11 nodes
│
├── scripts/
│   ├── setup_master.ps1  # Windows Master PC one-time setup (PowerShell)
│   ├── setup_worker.sh   # Jetson Nano one-time setup (Bash)
│   └── health_check.py   # CLI tool: query coordinator and probe RPC ports
│
└── tests/               # Unit and integration tests (no GPU required)
    ├── test_protocol.py
    ├── test_coordinator.py
    ├── test_llm_distributor.py
    └── test_pycuda_distributor.py
```

---

## Network topology

```
                  ┌─────────────────────┐
                  │  Windows Master PC  │
                  │  (CPU-only)         │
                  │  192.168.1.1        │
                  └────────┬────────────┘
                           │  1 Gbps switch
         ┌─────────────────┼──────────────────┐
         │                 │                  │
  ┌──────▼──────┐   ┌──────▼──────┐   ┌──────▼──────┐
  │ nano-01     │   │ nano-02     │   │  …           │
  │ 192.168.1.101│  │ 192.168.1.102│  │ nano-11      │
  └─────────────┘   └─────────────┘   └─────────────┘
```

Edit `config/cluster.yaml` to match your actual IP assignments.

---

## Quick start

### 1 — Master PC (Windows)

```powershell
# Install dependencies and llama.cpp CLI binary
.\scripts\setup_master.ps1

# Start the coordinator (keep this running)
python -m master.coordinator
```

### 2 — Each Jetson Nano

```bash
# One-time setup (installs llama-rpc-server, PyCUDA, systemd service)
./scripts/setup_worker.sh --master-host 192.168.1.1 --node-id nano-01

# Start the worker
sudo systemctl start jetson-nano-worker.service
# or directly:
python3 -m worker.worker --master-host 192.168.1.1 --node-id nano-01
```

### 3 — Health check

```bash
python scripts/health_check.py --master-host 192.168.1.1
```

Expected output:

```
NODE ID              HOST             STATUS     RPC PORT   RPC REACHABLE
----------------------------------------------------------------------
nano-01              192.168.1.101    online     50052      ✓
nano-02              192.168.1.102    online     50052      ✓
…
11/11 nodes online.
```

---

## LLM inference example

```python
from master.coordinator import Coordinator
from master.llm_distributor import LLMDistributor

# Assume coordinator is already running
coordinator = Coordinator()
dist = LLMDistributor(coordinator)

result = dist.infer(
    model_path="models/llama-3.1-8B-Q4_K_M.gguf",
    prompt="Explain unified memory in Jetson Nano.",
    max_tokens=256,
)
print(result["text"])
```

The master passes `-ngl 99` to `llama-cli` so *all* transformer layers are
computed on the Nano GPUs via the `--rpc` flag.  No GPU work runs on the
Master PC.

---

## PyCUDA workload example

```python
import numpy as np
from master.coordinator import Coordinator
from master.pycuda_distributor import PyCUDADistributor

coordinator = Coordinator()
dist = PyCUDADistributor(coordinator)

kernel = r"""
__global__ void vector_add(const float *a, const float *b, float *c, int n) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) c[i] = a[i] + b[i];
}
"""

n = 1024
a = np.ones(n, dtype=np.float32)
b = np.ones(n, dtype=np.float32) * 2.0

result = dist.dispatch(
    kernel_source=kernel,
    kernel_name="vector_add",
    inputs=[a, b, np.array([n], dtype=np.int32)],
    output_shape=[n],
    output_dtype="float32",
    grid=(n // 256 + 1, 1, 1),
    block=(256, 1, 1),
)
print(result)  # array of 3.0
```

The master serialises the kernel source and input arrays as base-64-encoded
JSON and sends them to an available Nano worker.  The worker compiles the
kernel with `pycuda.compiler.SourceModule`, executes it using UMA-optimised
memory (no redundant DMA copies), and returns the result.

---

## Wire protocol

All messages are JSON-encoded dictionaries framed with a 4-byte big-endian
`uint32` length prefix:

```
[ 4 bytes: body length ][ body_length bytes: UTF-8 JSON ]
```

See `shared/protocol.py` for the full set of message types
(`REGISTER`, `HEARTBEAT`, `TASK_SUBMIT`, `TASK_RESULT`, …).

---

## Running tests

Tests cover the protocol, coordinator, LLM distributor, and PyCUDA
distributor.  They do **not** require a GPU or llama.cpp binary.

```bash
pip install pytest numpy
python -m pytest tests/ -v
```

---

## Unified Memory Architecture (UMA) details

The Jetson Nano's Maxwell GPU does not have dedicated VRAM.  Instead, CPU and
GPU access the same 4 GB LPDDR4 pool.

| Operation | Discrete GPU | Jetson Nano UMA |
|---|---|---|
| `cudaMalloc` + `cudaMemcpy` | PCIe DMA transfer | In-place pointer remap |
| Page-locked (pinned) memory | Faster DMA | Zero-copy (same physical page) |
| Managed (`cudaMallocManaged`) | Page migration | Single allocation, no migration |

`worker/uma_utils.py` exposes helpers for all three allocation strategies.
The `llama-rpc-server` subprocess is launched with
`GGML_CUDA_ENABLE_UNIFIED_MEM=1` to hint the GGML CUDA backend to use
managed allocations.
