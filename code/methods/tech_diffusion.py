#!/usr/bin/env python3
"""
tech_diffusion.py — Technology Diffusion Model: spread of knowledge across strategies.

Tests P3 from the Anti-Dark-Forest framework: the Dark Forest strategy results
in slower technological advancement due to limited access to knowledge. Models
technology as a diffusing quantity across a civilisation graph where each node's
tech level grows based on: (a) internal R&D, (b) absorption from neighbours,
(c) strategy-dependent modifiers.

Dark Forest: no absorption (isolated), high R&D waste on weapons.
Assimilation: full absorption from all neighbours, R&D focused on compute.
Seeding: moderate absorption, balanced R&D.
"""
from __future__ import annotations

import numpy as np


def describe() -> str:
    return ("Technology Diffusion: rate of technological advancement under "
            "Dark Forest vs assimilation vs seeding strategies.")


def default_params() -> dict:
    return {
        "n_civ": 80,                  # number of civilisations
        "steps": 1000,                # simulation time steps
        "initial_tech": 1.0,          # starting technology level per civ
        "rd_base": 0.01,              # base internal R&D rate per step
        "absorption_rate": 0.03,      # fraction of neighbour tech gap absorbed
        "df_rd_penalty": 0.4,         # Dark Forest: fraction of R&D wasted on weapons
        "df_absorption": 0.0,         # Dark Forest: no absorption (isolated)
        "assim_rd_bonus": 1.5,        # Assimilation: R&D multiplier (compute focus)
        "assim_absorption": 1.0,      # Assimilation: full absorption
        "seed_rd_factor": 1.0,        # Seeding: baseline R&D
        "seed_absorption": 0.5,       # Seeding: moderate absorption
        "connectivity": 0.15,         # initial edge probability
        "seed": 42,
    }


def run(n_civ=80, steps=1000, initial_tech=1.0, rd_base=0.01,
        absorption_rate=0.03, df_rd_penalty=0.4, df_absorption=0.0,
        assim_rd_bonus=1.5, assim_absorption=1.0, seed_rd_factor=1.0,
        seed_absorption=0.5, connectivity=0.15, seed=42) -> dict:
    rng = np.random.default_rng(seed)

    # Shared initial graph
    A = (rng.random((n_civ, n_civ)) < connectivity).astype(float)
    np.fill_diagonal(A, 0)

    def simulate(rd_factor, absorption_frac) -> dict:
        tech = np.full(n_civ, initial_tech, dtype=float)
        history = np.zeros(steps)
        for t in range(steps):
            # Internal R&D
            rd_gain = rd_base * rd_factor * (1 + rng.random(n_civ) * 0.1)
            # Absorption from neighbours: gap-weighted
            neighbour_tech = A @ tech
            neighbour_count = A.sum(axis=1)
            with np.errstate(divide="ignore", invalid="ignore"):
                avg_neighbour = np.where(neighbour_count > 0,
                                         neighbour_tech / neighbour_count, 0)
            tech_gap = np.maximum(0, avg_neighbour - tech)
            absorption_gain = absorption_rate * absorption_frac * tech_gap
            # Update
            tech += rd_gain + absorption_gain
            # Diminishing returns at high tech
            tech = tech / (1 + tech * 0.001)
            history[t] = tech.mean()
        return {
            "final_tech_mean": float(tech.mean()),
            "final_tech_max": float(tech.max()),
            "final_tech_min": float(tech.min()),
            "tech_std": float(tech.std()),
            "history": history.tolist(),
        }

    df_result = simulate(df_rd_penalty, df_absorption)
    assim_result = simulate(assim_rd_bonus, assim_absorption)
    seed_result = simulate(seed_rd_factor, seed_absorption)

    assim_vs_df = assim_result["final_tech_mean"] / max(df_result["final_tech_mean"], 1e-9)
    assim_vs_seed = assim_result["final_tech_mean"] / max(seed_result["final_tech_mean"], 1e-9)

    return {
        "dark_forest": df_result,
        "assimilation": assim_result,
        "seeding": seed_result,
        "assimilation_vs_dark_forest_ratio": round(assim_vs_df, 3),
        "assimilation_vs_seeding_ratio": round(assim_vs_seed, 3),
        "verdict": (
            f"Assimilation achieves {assim_vs_df:.1f}x the technology level of "
            f"Dark Forest and {assim_vs_seed:.1f}x that of seeding. "
            f"Dark Forest R&D penalty ({df_rd_penalty}) and zero absorption "
            f"({df_absorption}) cripple advancement. Open knowledge diffusion "
            f"dominates closed strategies in technological growth rate."
        ),
    }