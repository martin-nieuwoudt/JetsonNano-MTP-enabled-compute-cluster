#!/usr/bin/env python3
"""
judge.py — Phase-3 judge for the 3-stage Anti-Dark Forest meta-loop.

Phase 3 is the load-bearing phase: all of Phase 1 (strategy) and Phase 2
(execution) converge here. The large model must:
  1. EVALUATE the theory against the empirical Phase-2 outputs, proposition by
     proposition (mapping from judge_rubric.PROPOSITIONS).
  2. CRITIQUE the mathematics of the harnesses (judge_rubric.CRITIQUE_RULES) —
     catch circularities where the verdict is baked into a constant.
  3. PROPOSE concrete manuscript/code improvements (from the same rules).

The judge is transport-agnostic: it takes a list of Phase-2 result dicts (each
carrying a `_method` tag from harness.run) and returns a structured verdict.
The actual "large model" call is pluggable (default: a deterministic rubric
evaluator; production swaps in the 70B / DeepSeek-R1-32B model via the MCP
server). All changeable logic lives in judge_rubric.py.

Output is JSON-serialisable so it can be written to the trace and fed back to
Phase 1 (re-strategize) or directly to the manuscript.
"""
from __future__ import annotations

import json
from typing import Dict, List

import judge_rubric as R


# ---------------------------------------------------------------------------
# 1. EVALUATE — proposition pass/fail against empirical metrics
# ---------------------------------------------------------------------------
_OPS = {
    "<": lambda a, b: a < b,
    ">": lambda a, b: a > b,
    "==": lambda a, b: abs(a - b) < 1e-9,
    "!=": lambda a, b: abs(a - b) >= 1e-9,
}


def _metric_index(results: List[Dict], method: str) -> Dict:
    """Return the first result dict tagged with _method == method."""
    for r in results:
        if isinstance(r, dict) and r.get("_method") == method:
            return r
    return {}


def _eval_condition(cond: Dict, prop: Dict, results: List[Dict]):
    """Evaluate one condition; return (ok, evidence_str)."""
    for m in prop["methods"]:
        res = _metric_index(results, m)
        if cond["metric"] in res:
            val = res[cond["metric"]]
            ok = _OPS[cond["op"]](val, cond["val"])
            ev = (f"{cond['metric']}={val:.4g} (via {m}) "
                  f"({'PASS' if ok else 'FAIL'} {cond['op']} {cond['val']})")
            return ok, ev
    return False, (f"{cond['metric']}: MISSING from any of {prop['methods']} "
                   f"(metric malformed or method not run)")


def evaluate_propositions(results: List[Dict]) -> List[Dict]:
    """Evaluate every proposition; return per-proposition pass/fail + evidence."""
    out = []
    for prop in R.PROPOSITIONS:
        evidence = []
        passed = True
        for cond in prop["conditions"]:
            ok, ev = _eval_condition(cond, prop, results)
            passed = passed and ok
            evidence.append(ev)
        out.append({
            "id": prop["id"],
            "statement": prop["statement"],
            "passed": passed,
            "evidence": evidence,
            "notes": prop["notes"],
        })
    return out


# ---------------------------------------------------------------------------
# 2. CRITIQUE — known mathematical weaknesses in the harnesses
# ---------------------------------------------------------------------------
def critique_methods(results: List[Dict]) -> List[Dict]:
    """Raise critique findings for every method present in the Phase-2 outputs.

    Rules flagged `resolved: True` in judge_rubric.py are skipped — they record
    the historical defect but no longer downgrade the verdict once the harness
    derives the value instead of hardcoding it.
    """
    present = {r.get("_method") for r in results if isinstance(r, dict)}
    findings = []
    for rule in R.CRITIQUE_RULES:
        if rule.get("resolved"):
            continue
        if rule["method"] in present:
            findings.append({
                "method": rule["method"],
                "severity": rule["severity"],
                "issue": rule["issue"],
                "proposed_fix": rule["proposed_fix"],
            })
    return findings


# ---------------------------------------------------------------------------
# 3. PROPOSE — aggregate critique into manuscript/code edit proposals
# ---------------------------------------------------------------------------
def propose_edits(findings: List[Dict]) -> List[Dict]:
    """Turn critique findings into ordered edit proposals (HIGH first)."""
    order = {"HIGH": 0, "MED": 1, "LOW": 2}
    ranked = sorted(findings, key=lambda f: order.get(f["severity"], 9))
    return [{
        "priority": f["severity"],
        "target_method": f["method"],
        "problem": f["issue"],
        "proposed_change": f["proposed_fix"],
    } for f in ranked]


# ---------------------------------------------------------------------------
# 4. BLIND SPOT — generic coverage audit (the "blind-spot agent" in Phase 3)
# Cross-references THEORY_CLAIMS -> PROPOSITIONS -> methods. Reports three gap
# classes the other passes miss:
#   - coverage_gap:   a claim the theory makes with NO proposition testing it
#   - evidence_gap:   a proposition covers the claim but its method returned no
#                     usable metric (malformed / not run) -> claim unverified
#   - orphan_compute: a method ran but supports no proposition (wasted Phase-2)
# ---------------------------------------------------------------------------
def _claim_verified(claim: Dict, prop_methods: Dict[str, set],
                    results: List[Dict]) -> bool:
    """True if any covering proposition's method ran and produced a metric."""
    for pid in claim.get("covered_by", []):
        for m in prop_methods.get(pid, set()):
            res = _metric_index(results, m)
            if any(k not in ("_method", "_params") for k in res):
                return True
    return False


def blind_spot(results: List[Dict]) -> Dict:
    """Audit theory coverage. Returns gap lists + a blind_spots_open flag."""
    present_methods = {r.get("_method") for r in results if isinstance(r, dict)}
    # Map proposition id -> set of methods that actually produced output.
    prop_methods: Dict[str, set] = {
        prop["id"]: {m for m in prop["methods"] if m in present_methods}
        for prop in R.PROPOSITIONS
    }

    coverage_gaps = []    # claim with covered_by == [] (nothing tests it)
    evidence_gaps = []    # claim covered, but covering prop's method gave no metric
    referenced = set()

    for claim in R.THEORY_CLAIMS:
        covers = claim.get("covered_by", [])
        if not covers:
            coverage_gaps.append({
                "claim": claim["id"],
                "statement": claim["statement"],
                "section": claim.get("section", ""),
                "gap": "no proposition tests this claim",
            })
            continue
        referenced.update(_methods_for_claim(covers, prop_methods))
        if not _claim_verified(claim, prop_methods, results):
            evidence_gaps.append({
                "claim": claim["id"],
                "statement": claim["statement"],
                "section": claim.get("section", ""),
                "covered_by": covers,
                "gap": "covering proposition produced no usable metric",
            })

    # Orphan compute: method present in results but referenced by no proposition.
    orphan_compute = [
        m for m in present_methods
        if m and not any(m in prop["methods"] for prop in R.PROPOSITIONS)
    ]

    return {
        "coverage_gaps": coverage_gaps,
        "evidence_gaps": evidence_gaps,
        "orphan_compute": orphan_compute,
        "blind_spots_open": bool(coverage_gaps or evidence_gaps),
        "claims_total": len(R.THEORY_CLAIMS),
        "claims_covered": sum(1 for c in R.THEORY_CLAIMS
                              if c.get("covered_by")),
    }


def _methods_for_claim(prop_ids: List[str], prop_methods: Dict[str, set]) -> set:
    """Flatten the method sets of the given proposition ids."""
    out: set = set()
    for pid in prop_ids:
        out.update(prop_methods.get(pid, set()))
    return out


# ---------------------------------------------------------------------------
# AGGREGATE — combine into a final stance per VERDICT_THRESHOLDS
# ---------------------------------------------------------------------------
def _aggregate(prop_results: List[Dict], findings: List[Dict],
               blind: Dict | None = None) -> Dict:
    n = len(prop_results)
    n_pass = sum(1 for p in prop_results if p["passed"])
    pass_frac = (n_pass / n) if n else 0.0
    high_open = any(f["severity"] == "HIGH" for f in findings)

    th = R.VERDICT_THRESHOLDS
    if n_pass == 0:
        stance = "REFUTED"
    elif pass_frac >= th["supported_min_pass_frac"]:
        stance = "SUPPORTED"
    elif pass_frac > 0.33:
        stance = "PARTIAL"
    else:
        stance = "INCONCLUSIVE"

    # A circular proof (uncorrected HIGH critique) can never SUPPORT a thesis.
    if th["cap_at_partial_if_high_critique"] and high_open and stance == "SUPPORTED":
        stance = "PARTIAL"
    # Open blind spots (untested theory claims) also cap confidence at PARTIAL:
    # you cannot claim SUPPORTED for a thesis whose own claims are unexamined.
    if blind and blind.get("blind_spots_open") and stance == "SUPPORTED":
        stance = "PARTIAL"

    return {
        "stance": stance,
        "propositions_passed": n_pass,
        "propositions_total": n,
        "pass_fraction": round(pass_frac, 3),
        "high_severity_circularities_open": high_open,
        "blind_spots_open": bool(blind and blind.get("blind_spots_open")),
    }


# ---------------------------------------------------------------------------
# PUBLIC ENTRY — judge(results) -> full Phase-3 verdict
# ---------------------------------------------------------------------------
def judge(results: List[Dict]) -> Dict:
    """Run the full Phase-3 evaluation on Phase-2 result dicts.

    results: list of dicts, each from harness.run (carries '_method' tag).
    Returns a structured verdict: propositions, critique, proposals, blind
    spots, and stance.
    """
    prop_results = evaluate_propositions(results)
    findings = critique_methods(results)
    proposals = propose_edits(findings)
    blind = blind_spot(results)
    agg = _aggregate(prop_results, findings, blind)

    return {
        "phase": 3,
        "propositions": prop_results,
        "critique": findings,
        "proposed_edits": proposals,
        "blind_spots": blind,
        "verdict": agg,
        "summary": (
            f"Thesis stance: {agg['stance']} "
            f"({agg['propositions_passed']}/{agg['propositions_total']} propositions "
            f"pass). "
            f"{len(findings)} mathematical critique finding(s); "
            f"{sum(1 for f in findings if f['severity']=='HIGH')} HIGH-severity "
            f"circularity/circular-proof issue(s) must be corrected before the "
            f"manuscript can claim support. "
            f"Blind-spot audit: {blind['claims_covered']}/{blind['claims_total']} "
            f"theory claims covered; {len(blind['coverage_gaps'])} coverage gap(s), "
            f"{len(blind['evidence_gaps'])} evidence gap(s)."
        ),
    }


def judge_to_json(results: List[Dict], path: str | None = None) -> str:
    """Run judge() and optionally write to path; always return JSON string."""
    out = judge(results)
    text = json.dumps(out, indent=2)
    if path:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return text


# ---------------------------------------------------------------------------
# PLUGGABLE LARGE-MODEL HOOK (production)
# ---------------------------------------------------------------------------
async def judge_with_model(results: List[Dict], big_model_fn) -> Dict:
    """Production path: feed the rubric-evaluated verdict to the large model for
    natural-language manuscript edits. big_model_fn(verdict_json) -> str edits.

    The deterministic judge() above is always run first (it is the audit trail);
    the model only adds prose. This keeps the evaluation reproducible and the
    model's role explicit (propose, not decide)."""
    base = judge(results)
    prose = await big_model_fn(json.dumps(base, indent=2))
    base["manuscript_edits"] = prose
    return base


if __name__ == "__main__":
    # Smoke test: run all 6 harnesses and judge them.
    import sys
    sys.path.insert(0, "../methods")
    import harness
    results = [harness.run_method(m, {}) for m in R.PROPOSITIONS and
               ["marl", "montecarlo", "thermo_ca", "kl_div", "lean", "bayesian"]]
    print(judge_to_json(results))
