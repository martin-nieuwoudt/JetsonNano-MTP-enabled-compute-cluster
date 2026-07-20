#!/usr/bin/env python3
"""
task_graph.py — Self-documenting DAG task model for the allocator.

Every task is a JSON object carrying its own audit trail. This is the single
schema shared between the orchestrator, the workers, and the trace exporter.

Schema (mirrors the allocator doc's Dynamic Task Graph):
  task_id              : str   — unique id, e.g. TASK_001_FIRST_STRIKE_MATH
  status               : str   — PENDING | RUNNING | DONE | FAILED
  required_capability  : str   — MATH | CODE | REASON | SYNTH  (affinity hint)
  target_model         : str   — registry key in mcp.cluster_config.MODELS
  dependencies         : list  — task_ids that must complete first (DAG edges)
  input_data           : str   — the prompt / payload (TEXT — LLMs receive text)
  fp16_instruction_b64 : str   — base64 float16 embedding of input_data (FP16 path)
  fp16_tokens           : int   — token count of the fp16 embedding (for decode)
  strategy_justification: str  — filled by orchestrator BEFORE dispatch (Pass 1)
  execution_log        : list  — append-only state changes (Pass 2)
  result               : str   — worker output (filled on completion)
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class Task:
    task_id: str
    required_capability: str
    target_model: str
    input_data: str
    status: str = "PENDING"
    dependencies: List[str] = field(default_factory=list)
    strategy_justification: str = ""
    fp16_instruction_b64: str = ""   # base64 float16 embedding of input_data
    fp16_tokens: int = 0              # token count of that embedding
    execution_log: List[Dict[str, str]] = field(default_factory=list)
    result: str = ""

    def log(self, stage: str, msg: str) -> None:
        """Append an immutable state-change record (Pass 2 self-doc)."""
        self.execution_log.append({
            "stage": stage,
            "timestamp": _now(),
            "msg": msg,
        })

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Task":
        return cls(**d)


def attach_fp16_instruction(task: "Task", embedding: "np.ndarray") -> None:
    """Attach a float16 embedding of the task's text instruction as the FP16
    companion payload. `embedding` is (num_tokens, EMBEDDING_DIM) float16.
    Imported lazily to keep task_graph import-light."""
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from mcp.embed_client import embedding_to_b64
    task.fp16_instruction_b64 = embedding_to_b64(embedding)
    task.fp16_tokens = int(embedding.shape[0])
    task.log("FP16_PAYLOAD",
             f"Attached float16 instruction embedding ({embedding.shape[0]}x"
             f"{embedding.shape[1]}, dtype={embedding.dtype})")


def make_task(capability: str, model: str, data: str,
              deps: List[str] | None = None,
              task_id: str | None = None) -> Task:
    """Convenience factory. Auto-generates an id if none given."""
    if task_id is None:
        task_id = f"TASK_{uuid.uuid4().hex[:8].upper()}"
    return Task(
        task_id=task_id,
        required_capability=capability,
        target_model=model,
        input_data=data,
        dependencies=deps or [],
    )


def affinity_key(task: Task) -> str:
    """Grouping key for the Stage-Gate scheduler: model + capability."""
    return f"{task.target_model}|{task.required_capability}"
