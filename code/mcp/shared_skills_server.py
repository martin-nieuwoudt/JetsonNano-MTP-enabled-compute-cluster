"""
shared_skills_server.py — Shared skills MCP server for ALL agents.

Plain FastMCP server (no NeMo Agent Toolkit workflow required). Exposes the
shared skills library to every agent — VS Code Copilot, hermes-*, and the
jetson-cluster MCP client — over streamable-http at http://localhost:9901/mcp.

Tool surface:
  skills.phase2_method            — run any of the 15 Phase 2 simulation methods
  skills.phase2_list_methods     — list the 15 methods + descriptions
  skills.recursive_entropy       — Recursive Entropy Optimizer convergence protocol
  skills.code_execution          — run a sandboxed Python snippet locally
  skills.current_datetime        — current date/time
  skills.current_timezone        — current timezone

Single sources of truth (do NOT duplicate):
  - Phase 2 methods: code/methods/harness.py (run_method / METHODS)
  - Recursive Entropy logic: code/nat_skills/skills/recursive_entropy.py (_compress)

Run:
  python shared_skills_server.py            # stdio
  python shared_skills_server.py --http     # streamable-http on :9901
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import subprocess
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

# --- Make code/methods importable (Phase 2 harness) ---
_METHODS_DIR = Path(__file__).resolve().parents[1] / "methods"
if str(_METHODS_DIR) not in sys.path:
    sys.path.insert(0, str(_METHODS_DIR))
from harness import METHODS, run_method  # noqa: E402

# --- Reuse the Recursive Entropy logic from the NAT skills module ---
_NAT_SKILLS = Path(__file__).resolve().parents[1] / "nat_skills" / "skills"
if str(_NAT_SKILLS) not in sys.path:
    sys.path.insert(0, str(_NAT_SKILLS))
from recursive_entropy import _compress  # noqa: E402

mcp = FastMCP("cluster-shared-skills", port=9901)

_METHOD_NAMES = list(METHODS.keys())
_PHASE2_METHOD_DOC = (
    "Run an Anti-Dark-Forest Phase 2 simulation method and return its result dict.\n\n"
    "Args:\n"
    "    method: One of: " + ", ".join(_METHOD_NAMES) + ".\n"
    "    overrides: JSON string of parameter overrides, e.g. {\"samples\": 5000, \"seed\": 7}.\n\n"
    "Returns JSON string of the method result."
)


# ===========================================================================
# Phase 2 simulation skills
# ===========================================================================
@mcp.tool()
def phase2_method(method: str, overrides: str = "{}") -> str:
    """Run an Anti-Dark-Forest Phase 2 simulation method and return its result dict."""
    if method not in _METHOD_NAMES:
        raise ValueError(f"unknown method '{method}'; known: {_METHOD_NAMES}")
    try:
        ov = json.loads(overrides) if overrides else {}
    except json.JSONDecodeError as e:
        raise ValueError(f"overrides must be valid JSON: {e}") from e
    result = run_method(method, ov or {})
    return json.dumps(result, default=str)


# Assign the dynamically-built docstring (method list is only known at import time).
phase2_method.__doc__ = _PHASE2_METHOD_DOC


@mcp.tool()
def phase2_list_methods() -> str:
    """List all available Phase 2 simulation methods and their one-line descriptions.

    Returns JSON: {"methods": [...], "descriptions": {name: desc}}.
    """
    import importlib

    descs: dict[str, str] = {}
    for name in _METHOD_NAMES:
        try:
            mod = importlib.import_module(name)
            descs[name] = (mod.describe() or "").splitlines()[0] if mod.describe() else ""
        except Exception:  # pragma: no cover - defensive
            descs[name] = ""
    return json.dumps({"methods": _METHOD_NAMES, "descriptions": descs}, default=str)


# ===========================================================================
# Recursive Entropy Optimizer
# ===========================================================================
@mcp.tool()
def recursive_entropy(text: str, task_type: str = "analytical", max_tokens: int = 400) -> str:
    """Apply the Recursive Entropy Optimizer's convergence protocol to a draft.

    Compresses free-text analysis into a high-density, actionable payload via
    initial synthesis -> divergent verification -> convergent synthesis ->
    dialectical audit.

    Args:
        text: The draft analysis / response to compress.
        task_type: One of: code, diagnostic, architecture, analytical, advisory.
        max_tokens: Soft ceiling on output token expenditure (quality floor preserved).

    Returns JSON: {"optimized": str, "efficiency_coefficient": float, "passes_applied": [...]}.
    """
    out = _compress(text, task_type, max_tokens)
    return json.dumps(
        {
            "optimized": out.optimized,
            "efficiency_coefficient": out.efficiency_coefficient,
            "passes_applied": out.passes_applied,
        }
    )


# ===========================================================================
# Core utility skills (NAT-free equivalents)
# ===========================================================================
@mcp.tool()
def code_execution(code: str, timeout: float = 30.0) -> str:
    """Execute a Python snippet in a local subprocess and return stdout/stderr/rc.

    Args:
        code: Python source to run.
        timeout: Seconds before the subprocess is killed.

    Returns JSON: {"returncode": int, "stdout": str, "stderr": str}.
    """
    try:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return json.dumps(
            {
                "returncode": proc.returncode,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
            }
        )
    except subprocess.TimeoutExpired as e:
        return json.dumps({"returncode": -1, "stdout": "", "stderr": f"timeout after {timeout}s: {e}"})


@mcp.tool()
def current_datetime() -> str:
    """Return the current local date and time as an ISO-8601 string."""
    return _dt.datetime.now().isoformat()


@mcp.tool()
def current_timezone() -> str:
    """Return the current local timezone name (e.g. 'Africa/Johannesburg')."""
    return str(_dt.datetime.now().astimezone().tzinfo)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Shared skills MCP server")
    parser.add_argument(
        "--http",
        action="store_true",
        help="Serve over streamable-http on :9901 instead of stdio.",
    )
    args = parser.parse_args()

    if args.http:
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
