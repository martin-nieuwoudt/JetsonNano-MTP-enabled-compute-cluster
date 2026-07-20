#!/usr/bin/env python3
"""
scheduler.py — Stage-Gate Macro-Scheduler (Paradigm A).

Implements the churn-prevention routing from the allocator doc:
  - Group the pending task queue by model affinity (target_model|capability).
  - For each group, drain it completely on nodes that already run that model
    (zero swap). Only if no affinity node is free do we issue a hot-swap
    intercept on an idle node.
  - A group is only dispatched once its DAG dependencies are DONE.
  - Nothing is fire-and-forget: a central queue holds undispatchable groups,
    so we never hit the 423 race condition of the naive poll script.

This module is transport-agnostic: it decides *who runs what*, and calls a
pluggable `dispatch(node, task)` coroutine you supply (e.g. HTTP POST to the
worker /execute endpoint, or a local dry-run).
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Awaitable, Callable, Dict, List, Optional

from task_graph import Task, affinity_key
from worker_state import NodeView, poll_cluster, affinity_match

DispatchFn = Callable[[NodeView, Task], Awaitable[None]]


class StageGateScheduler:
    def __init__(self, dispatch: DispatchFn):
        self._dispatch = dispatch
        self._queue: List[Task] = []
        self._done: Dict[str, Task] = {}
        # Track which model each node is currently committed to for the gate,
        # so we can report swaps accurately in the trace.
        self._node_model: Dict[str, str] = defaultdict(lambda: "None")

    def submit(self, task: Task) -> None:
        self._queue.append(task)

    def submit_many(self, tasks: List[Task]) -> None:
        self._queue.extend(tasks)

    def _deps_met(self, task: Task) -> bool:
        return all(d in self._done for d in task.dependencies)

    def _group_by_affinity(self) -> Dict[str, List[Task]]:
        groups: Dict[str, List[Task]] = defaultdict(list)
        for t in self._queue:
            if t.status == "PENDING" and self._deps_met(t):
                groups[affinity_key(t)].append(t)
        return groups

    async def run_gate(self) -> None:
        """Run one scheduling gate: poll, group, drain each group, swap at end."""
        nodes = await poll_cluster()
        idle_nodes = [n for n in nodes if n.idle]
        groups = self._group_by_affinity()

        for key, tasks in groups.items():
            target_model = tasks[0].target_model
            # 1) Prefer an idle node already running this model (zero swap).
            chosen = next((n for n in idle_nodes
                           if affinity_match(n, target_model)), None)
            swap_needed = chosen is None
            if chosen is None:
                # 2) Fall back to any idle node -> hot-swap intercept.
                chosen = next((n for n in idle_nodes), None)
            if chosen is None:
                # No capacity this gate; leave tasks queued for next gate.
                continue

            idle_nodes.remove(chosen)
            for task in tasks:
                task.status = "RUNNING"
                if swap_needed:
                    task.log("VRAM_EVICTION",
                             f"Hot-swap intercept: evict {self._node_model[chosen.ip]} "
                             f"-> {target_model} on {chosen.name}")
                else:
                    task.log("AFFINITY_HIT",
                             f"Zero-swap routing to {chosen.name} (already {target_model})")
                task.strategy_justification = (
                    f"Gate routed {key} to {chosen.name}: "
                    f"{'affinity (no swap)' if not swap_needed else 'hot-swap required'}. "
                    f"Group size={len(tasks)} drained before next swap."
                )
                await self._dispatch(chosen, task)
                task.status = "DONE"
                task.log("COMPLETED", f"Task finished on {chosen.name}")
                self._done[task.task_id] = task
            self._node_model[chosen.ip] = target_model
            # Remove drained tasks from the queue.
            self._queue = [t for t in self._queue if t.status != "DONE"]

    async def run_until_idle(self, gates: int = 50) -> None:
        for _ in range(gates):
            if not any(t.status == "PENDING" for t in self._queue):
                break
            await self.run_gate()
            await asyncio.sleep(0.05)  # yield; real deployments use a longer tick
