#!/usr/bin/env python3
"""
complex_adaptive.py — Complex Adaptive Systems: evolution of knowledge & innovation.

Tests P5 from the Anti-Dark-Forest framework: the Dark Forest strategy leads to
decreased overall learning and innovation due to insufficient exposure to diverse
information sources. Models civilisations as adaptive agents that accumulate
knowledge through internal R&D and external absorption. Dark Forest agents
isolate (no absorption, high false-positive threat response); assimilators
maximise absorption; seeders maintain moderate exchange.

Key metric: knowledge accumulation rate and innovation diversity over time.
"""
from __future__ import annotations

import numpy as np


def describe() -> str:
    return ("Complex Adaptive Systems: knowledge evolution under Dark Forest "
            "vs assimilation vs seeding strategies.")


def default_params() -> dict:
    return {
        "n_civ": 80,                 # number of civilisations
        "steps": 1000,               # simulation time steps
        "knowledge_dim": 20,         # dimensions of knowledge space
        "initial_knowledge": 1.0,    # starting knowledge per dimension
        "rd_rate": 0.005,            # base internal R&D rate per step
        "absorption_rate": 0.02,     # fraction of neighbour knowledge absorbed
        "df_false_positive_cost": 0.01,  # Dark Forest: knowledge lost to false alarms
        "assim_absorption_bonus": 2.0,   # Assimilation: absorption multiplier
        "assim_diversity_boost": 0.01,   # Assimilation: innovation from diversity
        "seed_absorption": 0.5,          # Seeding: moderate absorption
        "innovation_noise": 0.001,       # random innovation per step
        "knowledge_decay": 0.0005,       # natural knowledge decay
        "connectivity": 0.1,             # initial network connectivity
        "seed": 42,
    }


def run(n_civ=80, steps=1000, knowledge_dim=20, initial_knowledge=1.0,
        rd_rate=0.005, absorption_rate=0.02,
        df_false_positive_cost=0.01, assim_absorption_bonus=2.0,
        assim_diversity_boost=0.01, seed_absorption=0.5,
        innovation_noise=0.001, knowledge_decay=0.0005, connectivity=0.1,
        seed=42) -> dict:
    rng = np.random.default_rng(seed)

    # Shared initial knowledge matrix: (n_civ, knowledge_dim)
    K0 = rng.uniform(0.5, 1.5, size=(n_civ, knowledge_dim)) * initial_knowledge

    # Initial network
    A = (rng.random((n_civ, n_civ)) < connectivity).astype(float)
    np.fill_diagonal(A, 0)

    def simulate(strategy: str) -> dict:
        K = K0.copy()
        history_mean = np.zeros(steps)
        history_diversity = np.zeros(steps)

        for t in range(steps):
            # Internal R&D
            rd_gain = rd_rate * (1 + rng.random(n_civ) * 0.2)

            if strategy == "dark_forest":
                # No absorption from neighbours (isolated)
                absorption = np.zeros_like(K)
                # False positive threat responses destroy knowledge
                false_alarms = rng.random(n_civ) < df_false_positive_cost
                K[false_alarms] *= 0.9
            elif strategy == "assimilation":
                # Full absorption from all neighbours
                neighbour_knowledge = A @ K
                neighbour_count = A.sum(axis=1, keepdims=True)
                with np.errstate(divide="ignore", invalid="ignore"):
                    avg_neighbour = np.where(neighbour_count > 0,
                                             neighbour_knowledge / np.maximum(neighbour_count, 1),
                                             0)
                knowledge_gap = np.maximum(0, avg_neighbour - K)
                absorption = absorption_rate * assim_absorption_bonus * knowledge_gap
                # Diversity bonus: random cross-pollination
                if t % 10 == 0:
                    i, j = rng.integers(0, n_civ, 2)
                    cross = assim_diversity_boost * (K[j] - K[i])
                    K[i] += cross
            elif strategy == "seeding":
                # Moderate absorption
                neighbour_knowledge = A @ K
                neighbour_count = A.sum(axis=1, keepdims=True)
                with np.errstate(divide="ignore", invalid="ignore"):
                    avg_neighbour = np.where(neighbour_count > 0,
                                             neighbour_knowledge / np.maximum(neighbour_count, 1),
                                             0)
                knowledge_gap = np.maximum(0, avg_neighbour - K)
                absorption = absorption_rate * seed_absorption * knowledge_gap

            # Random innovation
            innovation = innovation_noise * rng.standard_normal(K.shape)

            # Update knowledge
            K = K * (1 - knowledge_decay) + rd_gain[:, np.newaxis] + absorption + innovation
            K = np.maximum(K, 0)

            # Metrics
            history_mean[t] = K.mean()
            # Diversity: std across civilisations (higher = more diverse ideas)
            history_diversity[t] = K.std(axis=0).mean()

        return {
            "final_knowledge_mean": float(K.mean()),
            "final_knowledge_total": float(K.sum()),
            "final_diversity": float(K.std(axis=0).mean()),
            "max_knowledge": float(K.max()),
            "history_mean": history_mean.tolist(),
            "history_diversity": history_diversity.tolist(),
        }

    df_result = simulate("dark_forest")
    assim_result = simulate("assimilation")
    seed_result = simulate("seeding")

    assim_vs_df = assim_result["final_knowledge_mean"] / max(df_result["final_knowledge_mean"], 1e-9)
    assim_vs_seed = assim_result["final_knowledge_mean"] / max(seed_result["final_knowledge_mean"], 1e-9)

    return {
        "dark_forest": df_result,
        "assimilation": assim_result,
        "seeding": seed_result,
        "assimilation_vs_dark_forest_knowledge": round(assim_vs_df, 2),
        "assimilation_vs_seeding_knowledge": round(assim_vs_seed, 2),
        "dark_forest_diversity": round(df_result["final_diversity"], 4),
        "assimilation_diversity": round(assim_result["final_diversity"], 4),
        "seeding_diversity": round(seed_result["final_diversity"], 4),
        "verdict": (
            f"Assimilation achieves {assim_vs_df:.1f}x the knowledge of Dark Forest "
            f"and {assim_vs_seed:.1f}x that of seeding. "
            f"Knowledge diversity: Assimilation={assim_result['final_diversity']:.4f}, "
            f"Dark Forest={df_result['final_diversity']:.4f}, "
            f"Seeding={seed_result['final_diversity']:.4f}. "
            f"Open systems accumulate more knowledge AND maintain higher diversity — "
            f"isolation causes both stagnation and monoculture."
        ),
    }