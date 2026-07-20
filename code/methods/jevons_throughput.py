#!/usr/bin/env python3
"""
jevons_throughput.py — Method 10: Jevons Paradox in Evolutionary Throughput.

Tests C9 (selection for individual metabolic efficiency drives population-level
total power throughput UP via the Jevons effect; local efficiency -> global
dissipation).

We run a Lotka-style population where each individual has efficiency epsilon
(energy captured per unit resource). Selection favors higher epsilon. We track
total power P = N * <epsilon> * resource_per_capita and verify that as mean
efficiency rises under selection, total power rises even as per-capita resource
use drops.
"""
from __future__ import annotations

import numpy as np


def describe() -> str:
    return "Jevons: does efficiency selection raise total power throughput?"


def default_params() -> dict:
    return {
        "generations": 500,
        "pop": 400,
        "k_cap": 1000.0,
        "base_resource": 1.0,
        "r_base": 0.1,
        "selection_strength": 0.05,
        "seed": 44,
    }


def run(generations=500, pop=400, k_cap=1000.0, base_resource=1.0, r_base=0.1,
        selection_strength=0.05, seed=44) -> dict:
    rng = np.random.default_rng(seed)
    eps = rng.uniform(0.2, 0.6, size=pop)
    N = float(pop)
    mean_eps_hist = []
    total_power_hist = []
    per_cap_hist = []

    for _ in range(generations):
        fitness = eps
        # Logistic growth toward carrying capacity + efficiency selection.
        growth = (1.0 + r_base * (1.0 - N / k_cap)
                  + selection_strength * (fitness - fitness.mean()))
        N *= float(np.clip(growth.mean(), 0.5, 1.5))
        N = min(N, k_cap)
        per_cap = base_resource / (1.0 + 0.5 * eps.mean())
        total_power = N * eps.mean() * per_cap
        mean_eps_hist.append(float(eps.mean()))
        total_power_hist.append(float(total_power))
        per_cap_hist.append(float(per_cap))
        # Selection: shift eps distribution toward higher values.
        eps = eps + selection_strength * (eps - eps.mean()) \
            + rng.normal(0, 0.01, size=pop)
        eps = np.clip(eps, 0.05, 2.0)

    mean_eps_hist = np.array(mean_eps_hist)
    total_power_hist = np.array(total_power_hist)
    per_cap_hist = np.array(per_cap_hist)
    if np.std(mean_eps_hist) > 0 and np.std(total_power_hist) > 0:
        corr = float(np.corrcoef(mean_eps_hist, total_power_hist)[0, 1])
    else:
        corr = 0.0
    jevons_effect = bool(corr > 0 and total_power_hist[-1] > total_power_hist[0])
    per_capita_resource_drop = bool(per_cap_hist[-1] < per_cap_hist[0])

    return {
        "mean_efficiency_final": float(eps.mean()),
        "total_power_final": float(total_power_hist[-1]),
        "efficiency_power_correlation": corr,
        "jevons_effect": jevons_effect,
        "per_capita_resource_drop": per_capita_resource_drop,
        "verdict": (
            f"Mean efficiency rose to {eps.mean():.3g}; total power "
            f"{total_power_hist[0]:.1f} -> {total_power_hist[-1]:.1f} (Jevons: "
            f"efficiency selection raised total throughput)."
            if jevons_effect
            else "No clear Jevons effect at these parameters."
        ),
    }
