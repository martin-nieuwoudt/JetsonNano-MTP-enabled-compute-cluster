#!/usr/bin/env python3
"""
trace.py — Self-documenting execution trace + Graphviz DOT exporter.

The allocator must "self document ... how it was allocating and at what stage
of the task" and "draw a graph of what it was doing" (allocator doc). This
module collects the immutable JSON audit trail and renders it as a DOT graph
showing nodes, the models they ran, and the task flow over gates.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List

from task_graph import Task


@dataclass
class Trace:
    tasks: List[Task] = field(default_factory=list)
    gates: List[Dict] = field(default_factory=list)  # per-gate allocation summary

    def record_gate(self, gate_index: int, allocations: List[Dict]) -> None:
        self.gates.append({"gate": gate_index, "allocations": allocations})

    def to_json(self, path: str) -> None:
        payload = {
            "tasks": [t.to_dict() for t in self.tasks],
            "gates": self.gates,
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def to_dot(self, path: str) -> None:
        """Render node -> model -> task allocation graph (Graphviz DOT)."""
        lines = ["digraph allocator {", "  rankdir=LR;", "  node [shape=box];"]
        # One cluster per worker node showing the model it ran and task ids.
        node_models: Dict[str, Dict[str, List[str]]] = {}
        for t in self.tasks:
            # strategy_justification records the node name in parentheses.
            node = "unknown"
            sj = t.strategy_justification
            if "(" in sj and ")" in sj:
                node = sj[sj.rfind("(") + 1:sj.rfind(")")]
            node_models.setdefault(node, {}).setdefault(t.target_model, []).append(t.task_id)

        for node, models in node_models.items():
            for model, task_ids in models.items():
                label = f"{node}\\n{model}\\n{len(task_ids)} task(s)"
                lines.append(f'  "{node}_{model}" [label="{label}"];')
                for tid in task_ids:
                    lines.append(f'  "{node}_{model}" -> "{tid}" [label="{tid}"];')
                    lines.append(f'  "{tid}" [label="{tid}\\n{t.status}", shape=ellipse];')

        # Gate timeline as a top-level chain.
        prev = None
        for g in self.gates:
            gid = f"gate{g['gate']}"
            gate_label = f"Gate {g['gate']}"
            lines.append(f'  "{gid}" [label="{gate_label}", shape=octagon, color=blue];')
            if prev:
                lines.append(f'  "{prev}" -> "{gid}";')
            prev = gid

        lines.append("}")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
