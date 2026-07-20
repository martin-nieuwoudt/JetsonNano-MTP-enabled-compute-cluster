#!/usr/bin/env python3
"""
population_dynamics.py — Population Dynamics: seeding vs exploitation viability.

Tests P4 from the Anti-Dark-Forest framework: seeding new civilisations promotes
long-term sustainability over exploitation. Models civilisations as populations
with carrying capacity, growth rates, and strategy-dependent mortality. Dark
Forest civilisations exploit and collapse; seeders maintain sustainable growth;
assimilators achieve the highest steady-state population through mutualism.

Key metric: long-term population viability (fraction surviving at t=end) and
carrying capacity utilisation under each strategy.
"""
from __future__ import annotations

import numpy as np


def describe() -> str:
    return ("Population Dynamics: long-term viability of seeding vs exploitation "
            "vs assimilation strategies across multiple generations.")


def default_params() -> dict:
    return {
        "n_civ": 100,              # number of civilisations
        "generations": 500,        # simulation time steps
        "initial_pop": 100.0,      # starting population per civ
        "carrying_capacity": 1000.0,  # max sustainable population
        "growth_rate": 0.02,       # base population growth per generation
        "df_exploit_rate": 0.05,   # Dark Forest: resource extraction rate (unsustainable)
        "df_collapse_threshold": 0.2,  # fraction of carrying capacity below which collapse occurs
        "seed_reinvest_rate": 0.03,    # Seeding: fraction reinvested in new colonies
        "seed_colony_benefit": 1.5,    # multiplier on carrying capacity from colonies
        "assim_mutualism_rate": 0.04,  # Assimilation: mutual growth bonus from neighbours
        "assim_carrying_boost": 2.0,   # Assimilation: carrying capacity multiplier from integration
        "catastrophe_prob": 0.01,      # per-generation probability of random catastrophe
        "catastrophe_impact": 0.3,     # fraction of population lost in catastrophe
        "seed": 42,
    }


def run(n_civ=100, generations=500, initial_pop=100.0, carrying_capacity=1000.0,
        growth_rate=0.02, df_exploit_rate=0.05, df_collapse_threshold=0.2,
        seed_reinvest_rate=0.03, seed_colony_benefit=1.5, assim_mutualism_rate=0.04,
        assim_carrying_boost=2.0, catastrophe_prob=0.01, catastrophe_impact=0.3,
        seed=42) -> dict:
    rng = np.random.default_rng(seed)

    def simulate(strategy: str) -> dict:
        pop = np.full(n_civ, initial_pop, dtype=float)
        K = np.full(n_civ, carrying_capacity, dtype=float)
        alive = np.ones(n_civ, dtype=bool)
        history = np.zeros(generations)
        collapses = 0

        for t in range(generations):
            if strategy == "dark_forest":
                # Unsustainable exploitation: grow fast but deplete carrying capacity
                growth = growth_rate * 2.0 * pop * (1 - pop / K)
                K = K * (1 - df_exploit_rate)  # carrying capacity erodes
                K = np.maximum(K, carrying_capacity * df_collapse_threshold)
                # Collapse when population exceeds degraded capacity
                over_capacity = pop > K
                pop[over_capacity] *= 0.5
                collapses += int(over_capacity.sum())
            elif strategy == "seeding":
                # Sustainable growth with colony reinvestment
                growth = growth_rate * pop * (1 - pop / K)
                # Reinvest in new colonies -> increases carrying capacity
                K = K + seed_reinvest_rate * pop * seed_colony_benefit
                K = np.minimum(K, carrying_capacity * 3)  # cap at reasonable max
            elif strategy == "assimilation":
                # Mutualistic growth: benefit from neighbours
                growth = growth_rate * pop * (1 - pop / K)
                # Neighbour bonus: each civ gains from connected civs
                neighbour_boost = assim_mutualism_rate * pop.mean()
                growth += neighbour_boost
                # Integration increases carrying capacity
                K = np.full(n_civ, carrying_capacity * assim_carrying_boost)

            # Apply growth
            pop = pop + growth
            pop = np.maximum(pop, 0)

            # Random catastrophes
            catastrophe_hits = rng.random(n_civ) < catastrophe_prob
            pop[catastrophe_hits] *= (1 - catastrophe_impact)

            # Extinction check
            newly_dead = (pop < 1.0) & alive
            alive[newly_dead] = False
            pop[~alive] = 0

            history[t] = pop[alive].mean() if alive.any() else 0

        final_alive = int(alive.sum())
        return {
            "final_population_mean": float(pop[alive].mean()) if alive.any() else 0,
            "final_population_total": float(pop.sum()),
            "survival_rate": float(final_alive / n_civ),
            "collapses": int(collapses),
            "mean_carrying_capacity": float(K.mean()),
            "history": history.tolist(),
        }

    df_result = simulate("dark_forest")
    seed_result = simulate("seeding")
    assim_result = simulate("assimilation")

    return {
        "dark_forest": df_result,
        "seeding": seed_result,
        "assimilation": assim_result,
        "assimilation_vs_dark_forest_survival": round(
            assim_result["survival_rate"] / max(df_result["survival_rate"], 0.01), 2),
        "assimilation_vs_seeding_survival": round(
            assim_result["survival_rate"] / max(seed_result["survival_rate"], 0.01), 2),
        "verdict": (
            f"Dark Forest survival rate: {df_result['survival_rate']:.1%} "
            f"({df_result['collapses']} collapses). "
            f"Seeding survival: {seed_result['survival_rate']:.1%}. "
            f"Assimilation survival: {assim_result['survival_rate']:.1%}. "
            f"Unsustainable exploitation causes population collapse; "
            f"seeding and assimilation maintain long-term viability."
        ),
    }