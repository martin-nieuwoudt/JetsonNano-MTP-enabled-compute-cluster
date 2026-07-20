#!/usr/bin/env python3
"""
phase1_strategy.py — SINGLE SOURCE OF TRUTH for Phase 1 (research strategy).

Phase 1 is the large model's job: define *what* to study and *how* the small
models will test it. This module holds that strategy as data so the orchestrator
and the judge share one authoritative definition (architectural invariant:
"Changeable logic is never hardcoded").

It decomposes the Anti-Dark-Forest theory into a research DAG with two axes:
  AXIS A — Comparative: Dark Forest actor vs Thermodynamic actor (Fermi paradox).
  AXIS B — Intrinsic: does the theory's own thermodynamic machinery hold?

Axis A is covered by the original 6 harnesses (P1-P6). Axis B was the blind-spot
gap; it is now closed by 5 new harnesses (P7-P11) wired to the 5 coverage-gap
claims (C1, C5, C8, C9, C18).

The DAG, the method specs, and the claim->method map all derive from
judge_rubric (PROPOSITIONS / THEORY_CLAIMS) so there is exactly one place to
edit when the theory evolves.
"""
from __future__ import annotations

from typing import Dict, List

import judge_rubric as R


# ---------------------------------------------------------------------------
# RESEARCH DAG — research questions the small models must answer, with
# dependencies. `method` names the harness that executes the leaf; `claims`
# lists the THEORY_CLAIMS it settles. `axis` tags Comparative vs Intrinsic.
# ---------------------------------------------------------------------------
RESEARCH_DAG: List[Dict] = [
    # --- AXIS A: Comparative (Fermi paradox case study) ---
    {"id": "Q1_EROI", "axis": "A", "method": "marl",
     "claims": ["C3_MEPP", "C6_ENERGY_RATE_DENSITY"],
     "question": "Does kinetic strike yield zero computational mass vs assimilation?"},
    {"id": "Q2_SEEDING", "axis": "A", "method": "montecarlo",
     "claims": ["C2_FRACTAL_FILLING", "C11_BOUNDED_MAXENT", "C17_KINETIC_ACCELERATION"],
     "question": "Is Heuristic Seeding a prerequisite for long-term universal mapping?"},
    {"id": "Q3_THERMO_FILTER", "axis": "A", "method": "thermo_ca",
     "claims": ["C3_MEPP", "C4_DISSIPATIVE_STRUCTURES", "C13_LANDAUER_TAX",
                "C14_TRANSPARENCY_LIMIT", "C15_BI_MODAL_SILENCE"],
     "question": "Are Dark Forest strikes thermodynamically visible / self-filtering?"},
    {"id": "Q4_INFO_TRANSPARENCY", "axis": "A", "method": "kl_div",
     "claims": ["C7_INFO_ENERGY_EQUIVALENCE", "C10_FREE_ENERGY_KL"],
     "question": "Does simulating chaos cost more than maintaining the incubator?"},
    {"id": "Q5_BAYES_BLINDNESS", "axis": "A", "method": "bayesian",
     "claims": ["C7_INFO_ENERGY_EQUIVALENCE", "C10_FREE_ENERGY_KL"],
     "question": "Does Dark Forest blind itself at higher energy than the Thermodynamic actor?"},
    {"id": "Q6_BI_MODAL_SILENCE", "axis": "A", "method": "thermo_ca",
     "claims": ["C12_IDENTITY_DELTA", "C13_LANDAUER_TAX", "C14_TRANSPARENCY_LIMIT",
                "C15_BI_MODAL_SILENCE", "C16_LOUD_TRANSIENT"],
     "question": "Does Substrate Succession produce Bi-Modal Silence (Mode 2)?"},

    # --- AXIS B: Intrinsic (the theory's own proof-of-necessity) ---
    {"id": "Q7_VIABILITY_KERNEL", "axis": "B", "method": "viability_kernel",
     "claims": ["C1_VIABILITY_KERNEL", "C11_BOUNDED_MAXENT"],
     "question": "Is the Viability Kernel a sparse, low-dimensional subset priced by a lethality multiplier?",
     "depends_on": []},
    {"id": "Q8_REPLICATION_THERMO", "axis": "B", "method": "replication_thermo",
     "claims": ["C5_ENGLAND_LOWER_BOUND"],
     "question": "Does self-replication dissipate at least England's bound, scaling with copied complexity?",
     "depends_on": []},
    {"id": "Q9_TIEP_LIFETIME", "axis": "B", "method": "tiep_lifetime",
     "claims": ["C8_STABILITY_CONSTRAINT_TIEP", "C4_DISSIPATIVE_STRUCTURES"],
     "question": "Does life maximize Time-Integrated Entropy Production, not peak rate?",
     "depends_on": []},
    {"id": "Q10_JEVONS_THROUGHPUT", "axis": "B", "method": "jevons_throughput",
     "claims": ["C9_JEVONS_PARADOX"],
     "question": "Does efficiency selection raise total population power throughput (Jevons)?",
     "depends_on": []},
    {"id": "Q11_RECURSIVE_VIABILITY", "axis": "B", "method": "recursive_viability",
     "claims": ["C18_RECURSIVE_VIABILITY"],
     "question": "Does identity I(t)=H-PD(t) converge to 0 (Informational Transparency)?",
     "depends_on": []},
]


# ---------------------------------------------------------------------------
# METHOD SPECS — the 5 new Axis-B harnesses, declared here so Phase 1 (the big
# model) can enumerate them uniformly. The actual compute lives in code/methods/.
# `metrics` lists the result keys the judge reads; `settles` lists the claims.
# ---------------------------------------------------------------------------
METHOD_SPECS: List[Dict] = [
    {"name": "viability_kernel", "proposition": "P7_VIABILITY_KERNEL",
     "metrics": ["viability_fraction", "effective_dimension", "lethality_multiplier"],
     "settles": ["C1_VIABILITY_KERNEL", "C11_BOUNDED_MAXENT"]},
    {"name": "replication_thermo", "proposition": "P8_REPLICATION_THERMO",
     "metrics": ["heat_measured", "heat_bound", "complexity_heat_correlation"],
     "settles": ["C5_ENGLAND_LOWER_BOUND"]},
    {"name": "tiep_lifetime", "proposition": "P9_TIEP_LIFETIME",
     "metrics": ["tiep_life", "tiep_fire", "lifetime_ratio", "life_maximizes_tiep"],
     "settles": ["C8_STABILITY_CONSTRAINT_TIEP", "C4_DISSIPATIVE_STRUCTURES"]},
    {"name": "jevons_throughput", "proposition": "P10_JEVONS_THROUGHPUT",
     "metrics": ["mean_efficiency_final", "total_power_final",
                 "efficiency_power_correlation", "jevons_effect"],
     "settles": ["C9_JEVONS_PARADOX"]},
    {"name": "recursive_viability", "proposition": "P11_RECURSIVE_VIABILITY",
     "metrics": ["identity_final", "pd_final", "converged_to_transparency"],
     "settles": ["C18_RECURSIVE_VIABILITY"]},
]


def claim_to_method() -> Dict[str, List[str]]:
    """Authoritative claim -> method map, derived from THEORY_CLAIMS."""
    out: Dict[str, List[str]] = {}
    prop_methods = {p["id"]: p["methods"] for p in R.PROPOSITIONS}
    for claim in R.THEORY_CLAIMS:
        methods: List[str] = []
        for pid in claim.get("covered_by", []):
            methods.extend(prop_methods.get(pid, []))
        out[claim["id"]] = sorted(set(methods))
    return out


def emit_dag() -> Dict:
    """Structured DAG for the orchestrator / big model to consume."""
    return {
        "axes": {"A_comparative": 6, "B_intrinsic": 5},
        "research_dag": RESEARCH_DAG,
        "method_specs": METHOD_SPECS,
        "claim_to_method": claim_to_method(),
        "coverage_gaps_closed": ["C1", "C5", "C8", "C9", "C18"],
    }


if __name__ == "__main__":
    import json
    print(json.dumps(emit_dag(), indent=2))
