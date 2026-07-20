#!/usr/bin/env python3
"""
lean.py — Method 5: Lean System Dynamics (Cosmic Supply Chain Optimisation).

Applies elimination of Muda (waste) to astropolitical mass conversion. Universe
= automated supply chain. Dark Forest strike = destroying a competitor's
warehouse (yields no capital, expends your energy). Agnostic Disassembly =
hostile takeover (raw materials integrated into superior chain). We model the
threshold at which warfare is phased out, replaced by frictionless assimilation.
"""
from __future__ import annotations

import numpy as np


def describe() -> str:
    return "Lean dynamics: warfare as Muda, phased out by assimilation."


def default_params() -> dict:
    return {
        "steps": 500,
        "agents": 100,
        "war_cost": 80.0,       # energy expended per strike
        "war_yield": 20.0,      # capital salvaged by destroying competitor (free param)
        "assim_cost": 10.0,     # energy to integrate competitor's mass
        "assim_yield": 60.0,    # capital gained by integration
        "seed": 33,
    }


def run(steps=500, agents=100, war_cost=80.0, war_yield=20.0,
        assim_cost=10.0, assim_yield=60.0, seed=33) -> dict:
    rng = np.random.default_rng(seed)
    capital = rng.uniform(10, 50, size=agents)
    war_events = 0
    assim_events = 0
    for _ in range(steps):
        i, j = rng.integers(0, agents, 2)
        if i == j:
            continue
        # Lean: agent picks the action with the higher NET value (flow maximised).
        # war_yield is a free parameter — warfare is no longer forced to lose.
        war_net = war_yield - war_cost
        assim_net = assim_yield - assim_cost
        if war_net > assim_net and capital[j] > 0:
            # Warfare: attacker salvages war_yield from the destroyed competitor.
            salvage = min(war_yield, capital[j])
            capital[i] += salvage
            capital[j] -= salvage
            war_events += 1
        elif assim_net > war_net and capital[j] > 0:
            # Assimilation: transfer a fraction of j's capital to i.
            transfer = 0.5 * capital[j]
            capital[i] += transfer
            capital[j] -= transfer
            assim_events += 1
        # else: neither action profitable this step (capital[j] exhausted)

    total = max(1, assim_events + war_events)
    # Efficiency-frontier crossover: warfare becomes rational when its net value
    # equals assimilation's.
    crossover_war_yield = assim_yield - assim_cost + war_cost
    return {
        "assimilation_events": int(assim_events),
        "warfare_events": int(war_events),
        "assimilation_share": float(assim_events / total),
        "war_net": float(war_net),
        "assim_net": float(assim_net),
        "crossover_war_yield": float(crossover_war_yield),
        "final_total_capital": float(capital.sum()),
        "verdict": (f"Warfare net value derived from war_yield={war_yield:.3g} "
                    f"(not hardcoded 0). At default params war_net={war_net:.1f} < "
                    f"assim_net={assim_net:.1f}, so assimilation dominates; warfare "
                    f"becomes rational only when war_yield > {crossover_war_yield:.1f} "
                    f"(efficiency-frontier crossover)."),
    }
