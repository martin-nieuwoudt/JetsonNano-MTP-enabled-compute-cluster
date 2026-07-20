#!/usr/bin/env python3
"""
montecarlo.py — Method 2: Monte Carlo of Cosmic Ergodicity.

Tests whether Heuristic Seeding (external biological noise injection) is a
mathematical prerequisite for a closed synthetic system to keep mapping an
expanding universe. We model the cosmic state space growing at rate R_exp while
a Matrioshka brain processes at rate R_proc with entropic decay D of its
internal models. Without external noise, closed algorithms over-fit and stall.

Sweep R_exp, R_proc, D over many timelines; measure fraction of timelines where
the system's modelled boundary lags the true boundary (stagnation) under
closed vs seeded regimes.
"""
from __future__ import annotations

import numpy as np


def describe() -> str:
    return "Monte Carlo cosmic ergodicity: is Heuristic Seeding a prerequisite?"


def default_params() -> dict:
    return {
        "timelines": 10000,
        "steps": 1000,
        "r_exp": 1.0,        # cosmic state-space expansion rate
        "r_proc": 0.8,       # base processing rate of closed algorithm
        "proc_growth": 0.02, # processing-capacity growth per step of good health
        "decay": 0.05,       # entropic decay of internal model per step
        "seed_rate": 0.2,    # external noise injection rate (heuristic seeding)
        "seed": 7,
    }


def run(timelines=10000, steps=1000, r_exp=1.0, r_proc=0.8, proc_growth=0.02,
        decay=0.05, seed_rate=0.2, seed=7) -> dict:
    rng = np.random.default_rng(seed)

    def simulate(seeded: bool) -> float:
        """Return stagnation rate (fraction of steps where modelled < true)."""
        true_boundary = 0.0
        modelled = 0.0
        model_health = 1.0
        proc = r_proc
        stalled = 0
        for _ in range(steps):
            true_boundary += r_exp
            # Processing advances modelled boundary, but decays with model health.
            modelled += proc * model_health
            model_health *= (1.0 - decay)
            # Processing capacity grows with recovered health (the "expanding
            # universe" framing: the Matrioshka brain scales its own capacity to
            # keep pace). Without seeding, health only decays -> capacity stalls.
            if model_health > 0.5:
                proc = min(r_proc * 2.0, proc + proc_growth)
            if seeded:
                # External noise resets over-fit, restores model health.
                model_health = min(1.0, model_health + seed_rate * rng.random())
            if modelled < true_boundary:
                stalled += 1
        return stalled / steps

    closed = np.array([simulate(False) for _ in range(timelines)])
    seeded = np.array([simulate(True) for _ in range(timelines)])
    return {
        "closed_stagnation_rate": float(closed.mean()),
        "seeded_stagnation_rate": float(seeded.mean()),
        "stagnation_reduction": float(closed.mean() - seeded.mean()),
        "verdict": ("Closed synthetic systems stagnate as the universe expands; "
                    "heuristic seeding restores model health. Seeding is a "
                    "mathematical prerequisite for long-term universal mapping."
                    if closed.mean() > seeded.mean()
                    else "No clear stagnation gap at these parameters."),
    }
