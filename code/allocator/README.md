# Allocator — Stage-Gate Macro-Scheduler (Paradigm A)

## Purpose
Dynamic task allocation + load balancing for the 11-node Jetson Nano cluster,
built to the spec in `Alllocator _ Load balancer.md`. This is **Paradigm A**:
each worker node runs a *whole small model* via llama.cpp RPC / FastAPI, and the
orchestrator routes tasks to nodes by **model affinity** to minimise model
swaps (transit time) and Ethernet churn.

Paradigm B (PyCUDA MoE expert-sharding ring) lives separately in
`../mcp/workers/` and is a future spike — see `ring_stub.py` here.

## The 3-stage meta-loop (from the allocator doc)
1. **Big model defines strategy** — given available methods (Monte Carlo, Lean,
   physics, maths), it produces a DAG of tasks + assigns each a required model.
2. **Small models execute** — workers drain their queues; at final integration
   they reflect on what could have been done better.
3. **Big model judges** — uses results to decide pass/fail and proposes manuscript
   edits.

## Core invariants (must never be violated)
- **Single source of truth**: node IPs, ports, model paths, shard counts all come
  from `mcp.cluster_config`. Nothing is hardcoded here.
- **1 copy of each model on node0's SSD**, NFS-exported to workers. The allocator
  never copies weights per-worker; it only *assigns* a model to a node and relies
  on the NFS mount (`MODEL_MOUNT_ON_WORKER`) being prewarmed.
- **Churn prevention (Stage-Gate)**: tasks are grouped by `target_model` affinity.
  A node only hot-swaps when its current affinity batch is fully drained. This
  protects MicroSD endurance and avoids cold-start thrash.
- **Self-documenting**: every task carries a `strategy_justification` and an
  `execution_log[]` array; the orchestrator emits an immutable JSON audit trace
  and a Graphviz DOT of what it allocated, when, and why.

## Module layout
- `worker_state.py`   — node health/state polling + capacity-aware affinity view
- `scheduler.py`      — Stage-Gate Macro-Scheduler: sort → group → drain → swap
- `task_graph.py`     — DAG task model (self-documenting JSON schema)
- `trace.py`          — execution trace collector + Graphviz DOT exporter
- `orchestrator.py`   — top-level driver wiring the 3-stage loop
- `ring_stub.py`      — Paradigm B placeholder (future spike, not wired in)

## Routing algorithm (capacity-aware least-request)
1. Poll all nodes (heartbeat: current_model, free_ram_mb, status).
2. For each affinity group, pick an IDLE node already running that model
   (zero swap). Else pick any IDLE node and issue a hot-swap intercept.
3. If no node is free, queue the group for the next gate (no race-condition 423s
   — we use a central queue, not fire-and-forget HTTP).
4. Emit strategy_justification + append to execution_log at every state change.
