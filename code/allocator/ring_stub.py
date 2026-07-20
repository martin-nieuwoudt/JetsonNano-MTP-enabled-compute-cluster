#!/usr/bin/env python3
"""
ring_stub.py — Paradigm B (MoE expert-sharding ring) placeholder.

This is a FUTURE SPIKE, intentionally NOT wired into the allocator's main loop.
Paradigm A (independent whole-model agents, scheduler.py) is the day-one build
because it maps 1:1 to the 3-stage meta-loop and the 6 methodology personas.

Paradigm B would instead shard ONE MoE (e.g. Codestral-22B / DeepSeek-Coder-V2-Lite)
across the 11 nodes via a PyCUDA ring-pipeline: the orchestrator PC runs
attention + routing + LM-head, and the Jetsons run raw CUDA FFN expert kernels
in a double-buffered ring to hide 1GbE latency. The actual worker kernels already
exist in ../mcp/workers/jetson_ring_worker.py — this stub only records the
integration contract so the two paradigms stay clearly separated.

Integration contract (when/if activated):
  - The orchestrator would expose a `RingBackend` implementing the same
    `dispatch(node, task)` interface as scheduler.DispatchFn, but instead of
    POSTing a task to a node it would stream hidden-state tensors around the
    ring and collect the final tensor from the last Jetson.
  - Model selection becomes "which MoE + how to shard experts" rather than
    "which small model per node". The MODELS registry already tags MoE entries
    (kind="moe") so the scheduler can branch on that flag later.
  - Churn-prevention is moot for Paradigm B (weights are pinned per node for the
    life of the job), which is exactly why it's attractive for long homogeneous
    runs — but it does NOT give you 10 independent agent personas.
"""
from __future__ import annotations

RING_BACKEND_STATUS = "STUB"  # not active


def describe() -> str:
    return (
        "Paradigm B (MoE ring) is a stub. Activate only after Paradigm A proves "
        "the 3-stage loop on real hardware. Worker kernels: ../mcp/workers/"
        "jetson_ring_worker.py. Orchestrator head/tail: see memory sharding.txt."
    )


if __name__ == "__main__":
    print(describe())
