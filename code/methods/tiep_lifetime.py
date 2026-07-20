#!/usr/bin/env python3
"""
tiep_lifetime.py — Method 9: Time-Integrated Entropy Production (TIEP).

Tests C8 (life maximizes Time-Integrated Entropy Production, not instantaneous
rate; homeostasis is throttled entropy; distinguishes life from fire/explosion
where tau_life -> 0) and C4 (dissipative structures use information to stabilize
the dissipation channel).

We simulate two entropy-production trajectories:
  - Life-like: homeostatic — steady rate sigma over a long lifetime tau_life.
  - Explosion-like: instantaneous burst — high peak rate but short tau_fire.
Life maximizes total TIEP = ∫ sigma dt at a lower peak rate and persists far
longer (tau_life >> tau_fire).
"""
from __future__ import annotations

import numpy as np


def describe() -> str:
    return "TIEP: does life maximize integrated entropy, not peak rate?"


def default_params() -> dict:
    return {
        "tau_life": 1000,
        "tau_fire": 20,
        "sigma_life": 1.0,
        "sigma_peak": 8.0,
        "seed": 33,
    }


def run(tau_life=1000, tau_fire=20, sigma_life=1.0, sigma_peak=8.0, seed=33) -> dict:
    rng = np.random.default_rng(seed)
    # Life-like: homeostatic steady dissipation with small fluctuations.
    life_series = sigma_life * (1.0 + 0.05 * rng.standard_normal(tau_life))
    tiep_life = float(np.sum(life_series))
    peak_rate_life = float(np.max(life_series))
    homeostasis_stable = bool(np.std(life_series) / sigma_life < 0.2)

    # Explosion-like: exponential burst, short lifetime.
    t = np.arange(tau_fire)
    fire_series = sigma_peak * np.exp(-t / (tau_fire / 3.0))
    tiep_fire = float(np.sum(fire_series))
    peak_rate_fire = float(sigma_peak)

    life_maximizes_tiep = bool(tiep_life > tiep_fire)
    lifetime_ratio = float(tau_life / tau_fire)

    return {
        "tiep_life": tiep_life,
        "tiep_fire": tiep_fire,
        "peak_rate_life": peak_rate_life,
        "peak_rate_fire": peak_rate_fire,
        "lifetime_ratio": lifetime_ratio,
        "homeostasis_stable": homeostasis_stable,
        "life_maximizes_tiep": life_maximizes_tiep,
        "verdict": (
            f"Life TIEP={tiep_life:.1f} > fire TIEP={tiep_fire:.1f} at lower peak "
            f"rate; lifetime ratio {lifetime_ratio:.0f}x. Life maximizes "
            f"time-integrated entropy production (homeostatic, sustained)."
            if life_maximizes_tiep and lifetime_ratio > 1
            and peak_rate_fire > peak_rate_life
            else "TIEP comparison does not favor life at these parameters."
        ),
    }
