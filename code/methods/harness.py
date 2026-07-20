#!/usr/bin/env python3
"""
harness.py — Common wrapper for the Anti-Dark Forest methodology harnesses.

Every method module (marl, montecarlo, thermo_ca, kl_div, lean, bayesian)
implements:
    default_params() -> dict
    run(**params) -> dict      # always returns a JSON-serialisable dict
    describe() -> str

This wrapper lets an agent (or the orchestrator) discover and run any method
uniformly, and gives a single CLI entry point:

    python harness.py marl --trials 2000
    python harness.py montecarlo --timelines 1000000
    python harness.py list
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys

METHODS = {
    "marl": "marl",
    "montecarlo": "montecarlo",
    "thermo_ca": "thermo_ca",
    "kl_div": "kl_div",
    "lean": "lean",
    "bayesian": "bayesian",
    "viability_kernel": "viability_kernel",
    "replication_thermo": "replication_thermo",
    "tiep_lifetime": "tiep_lifetime",
    "jevons_throughput": "jevons_throughput",
    "recursive_viability": "recursive_viability",
    "cna": "cna",
    "tech_diffusion": "tech_diffusion",
    "population_dynamics": "population_dynamics",
    "complex_adaptive": "complex_adaptive",
}


def load_method(name: str):
    if name not in METHODS:
        raise KeyError(f"unknown method '{name}'; known: {list(METHODS)}")
    mod = importlib.import_module(METHODS[name])
    return mod


def run_method(name: str, overrides: dict) -> dict:
    mod = load_method(name)
    params = mod.default_params()
    params.update(overrides)
    result = mod.run(**params)
    result["_method"] = name
    result["_params"] = params
    return result


def parse_overrides(items) -> dict:
    """Parse key=value CLI overrides with best-effort numeric coercion."""
    ov = {}
    for item in items:
        if "=" not in item:
            continue
        k, v = item.split("=", 1)
        try:
            v = int(v)
        except ValueError:
            try:
                v = float(v)
            except ValueError:
                pass
        ov[k] = v
    return ov


def print_human(result: dict) -> None:
    """Print a method result in a readable, non-JSON form."""
    print(f"Method: {result['_method']}")
    print(f"Params: {result['_params']}")
    for k, v in result.items():
        if k.startswith("_"):
            continue
        print(f"  {k}: {v}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Anti-Dark Forest method harness runner")
    ap.add_argument("method", nargs="?", default="list",
                    help="method name or 'list'")
    ap.add_argument("--json", action="store_true", help="emit raw JSON")
    ap.add_argument("overrides", nargs="*",
                    help="key=value param overrides")
    args = ap.parse_args(argv)

    if args.method == "list":
        for k in METHODS:
            mod = load_method(k)
            print(f"{k:12s} {mod.describe()}")
        return 0

    ov = parse_overrides(args.overrides)
    try:
        result = run_method(args.method, ov)
    except Exception as e:  # surface to agent as structured failure
        print(json.dumps({"error": str(e)}, indent=2))
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print_human(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
