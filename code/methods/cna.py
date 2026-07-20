#!/usr/bin/env python3
"""
cna.py — Complex Network Analysis: information spread through civilisation networks.

Tests P2 from the Anti-Dark-Forest framework: civilisations engaging in
assimilation will have greater informational growth compared to those relying
solely on seeding. Models civilisations as nodes in a directed graph where
edges represent information flow. Dark Forest nodes sever edges (isolate);
assimilators add edges (connect); seeders maintain static topology.

Key metric: network information density (total unique information reachable
per node) over time. Dark Forest isolation reduces density; assimilation
increases it exponentially through transitive closure.
"""
from __future__ import annotations

import numpy as np


def describe() -> str:
    return ("Complex Network Analysis: information spread through civilisation "
            "networks under Dark Forest vs assimilation vs seeding strategies.")


def default_params() -> dict:
    return {
        "n_civ": 100,              # number of civilisations in the network
        "steps": 500,              # simulation time steps
        "initial_edge_prob": 0.1,  # probability of initial connection between any two civs
        "info_per_civ": 100.0,     # unique information units each civ starts with
        "df_sever_rate": 0.05,     # Dark Forest: probability of severing an edge per step
        "assim_add_rate": 0.08,    # Assimilation: probability of adding an edge per step
        "info_decay": 0.001,       # natural information decay per step
        "info_gain_factor": 0.02,  # fraction of neighbour's info gained per connected edge
        "seed": 42,
    }


def run(n_civ=100, steps=500, initial_edge_prob=0.1, info_per_civ=100.0,
        df_sever_rate=0.05, assim_add_rate=0.08, info_decay=0.001,
        info_gain_factor=0.02, seed=42) -> dict:
    rng = np.random.default_rng(seed)

    def simulate(strategy: str) -> dict:
        """Run one strategy and return info density history + final metrics."""
        # Adjacency matrix: A[i,j] = 1 if i receives info from j
        A = (rng.random((n_civ, n_civ)) < initial_edge_prob).astype(float)
        np.fill_diagonal(A, 0)  # no self-loops
        info = np.full(n_civ, info_per_civ, dtype=float)
        history = np.zeros(steps)

        for t in range(steps):
            if strategy == "dark_forest":
                # Sever edges probabilistically — isolation increases
                mask = rng.random((n_civ, n_civ)) < df_sever_rate
                A[mask] = 0
            elif strategy == "assimilation":
                # Add edges probabilistically — connectivity grows
                mask = rng.random((n_civ, n_civ)) < assim_add_rate
                A[mask] = 1
                np.fill_diagonal(A, 0)
            # else "seeding": static topology, no edge changes

            # Information flow: each civ gains fraction of neighbours' info
            info_in = A @ info * info_gain_factor
            info = info * (1 - info_decay) + info_in
            # Cap at reasonable maximum
            info = np.clip(info, 0, info_per_civ * 10)
            history[t] = info.mean()

        # Network metrics
        degrees = A.sum(axis=1)
        return {
            "final_info_density": float(info.mean()),
            "total_info": float(info.sum()),
            "mean_degree": float(degrees.mean()),
            "isolated_nodes": int((degrees == 0).sum()),
            "max_info": float(info.max()),
            "history": history.tolist(),
        }

    df_result = simulate("dark_forest")
    assim_result = simulate("assimilation")
    seed_result = simulate("seeding")

    # Key comparison: assimilation vs dark_forest info density ratio
    assim_vs_df = assim_result["final_info_density"] / max(df_result["final_info_density"], 1e-9)
    assim_vs_seed = assim_result["final_info_density"] / max(seed_result["final_info_density"], 1e-9)

    return {
        "dark_forest": df_result,
        "assimilation": assim_result,
        "seeding": seed_result,
        "assimilation_vs_dark_forest_ratio": round(assim_vs_df, 3),
        "assimilation_vs_seeding_ratio": round(assim_vs_seed, 3),
        "verdict": (
            f"Assimilation achieves {assim_vs_df:.1f}x the information density of "
            f"Dark Forest and {assim_vs_seed:.1f}x that of seeding. "
            f"Dark Forest isolates {df_result['isolated_nodes']} nodes; "
            f"assimilation isolates {assim_result['isolated_nodes']}. "
            f"Open networks dominate closed ones in information-theoretic throughput."
        ),
    }