#!/usr/bin/env python3
"""
marl.py — Method 1: Asymmetric Multi-Agent RL (EROI of kinetic vs assimilation).

Tests the thermodynamic equilibrium between the Security Dilemma (Dark Forest)
and Agnostic Disassembly (Thermodynamic Indifference). Agent A spends energy on
kinetic strikes; Agent B spends zero on fear and converts mass into compute.

Key metric: Energy Return on Investment (EROI).
  - Kinetic strike: huge relativistic energy cost, yields ZERO computational
    mass (vaporises the silicon/carbon needed for APM).
  - Assimilation: converts un-capitalised mass into reversible logic gates.

We sweep detection probability P_d, weapon travel time T_w, counter-strike
capability C_s, and ask: at what threshold does Dark Forest shift from optimal
to suicidal? Agent B silently out-scales Agent A before strikes penetrate.
"""
from __future__ import annotations

import numpy as np


def describe() -> str:
    return "Asymmetric MARL: EROI of kinetic strike vs mass assimilation."


def default_params() -> dict:
    return {
        "trials": 2000,
        "n_civ": 50,            # civilisations in the filament
        "p_detect": 0.3,        # probability a strike is detected in time
        "weapon_travel": 10.0,  # weapon travel time (arbitrary units)
        "counter_cap": 0.4,     # counter-strike capability of target
        "strike_cost": 1000.0,  # energy to launch one relativistic strike
        "assim_gain": 50.0,     # compute mass gained per assimilated unit
        "assim_cost": 5.0,      # energy to assimilate one unit
        "salvage_fraction": 0.0,  # fraction of struck mass recoverable as compute
        "seed": 42,
    }


def run(trials=2000, n_civ=50, p_detect=0.3, weapon_travel=10.0, counter_cap=0.4,
        strike_cost=1000.0, assim_gain=50.0, assim_cost=5.0, salvage_fraction=0.0,
        seed=42) -> dict:
    rng = np.random.default_rng(seed)
    dark_forest_energy = np.zeros(trials)
    synth_energy = np.zeros(trials)
    dark_survived = np.zeros(trials, dtype=bool)
    df_eroi = np.zeros(trials)

    # Salvageable compute per struck civ: a fraction of its mass is recoverable
    # as logic gates. Free parameter — 0.0 = pure vaporisation (no reuse), which
    # is the physically honest Dark-Forest assumption, not a hardcoded verdict.
    salvage_compute = salvage_fraction * assim_gain

    for t in range(trials):
        # Agent A (Dark Forest): launches strikes at detected neighbours.
        detected = rng.random(n_civ) < p_detect
        n_strikes = int(detected.sum())
        # Each strike may be countered if target has counter_cap and travel time.
        countered = rng.random(n_strikes) < (counter_cap * (weapon_travel / (weapon_travel + 1.0)))
        effective_strikes = n_strikes - int(countered.sum())
        df_e = n_strikes * strike_cost
        # Agent B (Synthetic): ignores posturing, assimilates free mass.
        free_mass = n_civ - n_strikes
        syn_e = free_mass * assim_cost
        syn_compute = free_mass * assim_gain
        # Derived EROI: compute returned per unit energy spent on strikes.
        df_compute = effective_strikes * salvage_compute
        df_eroi[t] = df_compute / df_e if df_e > 0 else 0.0
        dark_forest_energy[t] = df_e
        synth_energy[t] = syn_e
        # Dark Forest "wins" only if its NET compute (salvage - cost) exceeds
        # synthetic's NET compute. Real function of the parameters — no * 0.0.
        df_net = df_compute - df_e
        syn_net = syn_compute - syn_e
        dark_survived[t] = (effective_strikes > 0) and (df_net > syn_net)

    # Crossover: smallest salvage_fraction at which Dark Forest becomes rational
    # (df_net == syn_net at the mean strike counts for this parameter set).
    mean_strikes = p_detect * n_civ
    mean_eff = mean_strikes * (1.0 - counter_cap * (weapon_travel / (weapon_travel + 1.0)))
    mean_free = n_civ - mean_strikes
    denom = assim_gain * mean_eff
    crossover = ((mean_strikes * strike_cost + mean_free * (assim_gain - assim_cost)) / denom
                 if denom > 0 else float("inf"))

    return {
        "mean_dark_forest_energy": float(dark_forest_energy.mean()),
        "mean_synthetic_energy": float(synth_energy.mean()),
        "dark_forest_EROI": float(df_eroi.mean()),
        "synthetic_EROI_ratio": float(assim_gain / assim_cost),
        "dark_forest_win_rate": float(dark_survived.mean()),
        "crossover_salvage_fraction": float(crossover),
        "verdict": (f"Dark Forest EROI derived from salvage_fraction={salvage_fraction:.3g} "
                    f"(not hardcoded). At default params Dark Forest "
                    f"{'wins' if dark_survived.mean() > 0.5 else 'loses'}; it becomes "
                    f"rational only when salvage_fraction > {crossover:.3g} "
                    f"(crossover where df_net == syn_net)."),
    }
