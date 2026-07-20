"""phase2_methods.py — Wrap the Anti-Dark-Forest Phase 2 methodology harness
as NeMo Agent Toolkit functions so every agent (Copilot, hermes-*, jetson-cluster)
can call them through one shared MCP server.

Each method module in code/methods implements:
    default_params() -> dict
    run(**params) -> dict
    describe() -> str
This module registers one NAT function per method, dispatching through
code/methods/harness.py::run_method().
"""
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

import nat.plugin_api as plugin_api
from nat.builder.function import FunctionBaseConfig, FunctionInfo

# Make code/methods importable from this package.
_METHODS_DIR = Path(__file__).resolve().parents[2] / "methods"
if str(_METHODS_DIR) not in sys.path:
    sys.path.insert(0, str(_METHODS_DIR))

from harness import METHODS, run_method  # noqa: E402

_METHOD_NAMES = list(METHODS.keys())


class Phase2MethodConfig(FunctionBaseConfig, name="phase2_method"):
    """Generic config for any Phase 2 simulation method.

    The method name is selected at call time via the input schema, so a single
    registered function exposes all 15 methods. This keeps the MCP tool surface
    flat and discoverable rather than 15 near-identical entries.
    """
    pass


class Phase2MethodInput(BaseModel):
    method: str = Field(
        description=(
            "Name of the simulation method to run. One of: "
            + ", ".join(_METHOD_NAMES)
        ),
    )
    overrides: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional parameter overrides, e.g. {\"samples\": 5000, \"seed\": 7}.",
    )


class Phase2MethodOutput(BaseModel):
    method: str
    result: dict[str, Any]


@plugin_api.register_function(config_type=Phase2MethodConfig)
async def phase2_method(config: Phase2MethodConfig, builder):
    async def _run(inp: Phase2MethodInput) -> Phase2MethodOutput:
        if inp.method not in _METHOD_NAMES:
            raise ValueError(
                f"unknown method '{inp.method}'; known: {_METHOD_NAMES}"
            )
        # Offload the numpy-heavy sim off the event loop.
        result = await asyncio.to_thread(run_method, inp.method, inp.overrides or {})
        return Phase2MethodOutput(method=inp.method, result=result)

    yield FunctionInfo.from_fn(
        _run,
        description=(
            "Run an Anti-Dark-Forest Phase 2 simulation method and return its "
            "result dict. Methods: " + ", ".join(_METHOD_NAMES) + "."
        ),
        input_schema=Phase2MethodInput,
    )


class Phase2ListConfig(FunctionBaseConfig, name="phase2_list_methods"):
    pass


class Phase2ListInput(BaseModel):
    pass


class Phase2ListOutput(BaseModel):
    methods: list[str]
    descriptions: dict[str, str]


@plugin_api.register_function(config_type=Phase2ListConfig)
async def phase2_list_methods(config: Phase2ListConfig, builder):
    import importlib

    async def _list(inp: Phase2ListInput) -> Phase2ListOutput:
        def _collect() -> dict[str, str]:
            descs: dict[str, str] = {}
            for name in _METHOD_NAMES:
                try:
                    mod = importlib.import_module(name)
                    descs[name] = mod.describe()
                except Exception:  # pragma: no cover - defensive
                    descs[name] = ""
            return descs

        descs = await asyncio.to_thread(_collect)
        return Phase2ListOutput(methods=_METHOD_NAMES, descriptions=descs)

    yield FunctionInfo.from_fn(
        _list,
        description="List all available Phase 2 simulation methods and their descriptions.",
        input_schema=Phase2ListInput,
    )
