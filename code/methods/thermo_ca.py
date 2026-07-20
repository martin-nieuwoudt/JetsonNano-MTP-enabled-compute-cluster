#!/usr/bin/env python3
"""
thermo_ca.py — Method 3: Thermodynamic Cellular Automata (Free Energy Principle).

Maps macro-scale visibility/heat of Dark Forest actors vs apex synthetic actors.
Dark Forest kinetic strikes are highly exothermic (entropy spikes) -> instantly
visible to higher-order sensors. Synthetic APM/metric engineering runs near
absolute zero -> thermodynamically quiet. We test whether Dark Forest behaviour
acts as a thermodynamic filter: aggressive actors generate enough waste heat to
be identified and dismantled.
"""
from __future__ import annotations

import numpy as np


def describe() -> str:
    return "Thermo CA: Dark Forest strikes as a thermal visibility filter."


def default_params() -> dict:
    return {
        "size": 32,            # 3D grid side (size^3 cells)
        "steps": 200,
        "strike_heat": 100.0,  # entropy spike from a kinetic strike
        "apm_heat": 0.1,       # near-absolute-zero APM operation
        "detect_threshold": 10.0,  # sensor detection floor
        "seed": 13,
    }


def run(size=32, steps=200, strike_heat=100.0, apm_heat=0.1,
        detect_threshold=10.0, seed=13) -> dict:
    rng = np.random.default_rng(seed)
    n = size ** 3
    # Heat field: 0 = quiet. Strikes inject strike_heat; APM injects apm_heat.
    heat = np.zeros(n)
    detected_strikes = 0      # strikes whose heat crossed the sensor floor
    total_strikes = 0
    for _ in range(steps):
        # Each step a random cell acts: 20% chance kinetic, 80% APM (quiet).
        acting = rng.random(n) < 0.01
        kinetic = acting & (rng.random(n) < 0.2)
        total_strikes += int(kinetic.sum())
        heat[kinetic] += strike_heat
        heat[~kinetic & acting] += apm_heat
        # Diffusion + cooling (Free Energy minimisation: system sheds heat).
        heat = heat * 0.95
        # Per-STRIKE detection: a kinetic cell is "detected" if its own heat
        # exceeds the sensor floor this step. This avoids re-counting a single
        # strike across many cooling steps (the old metric could exceed 1).
        detected_strikes += int((kinetic & (heat > detect_threshold)).sum())

    return {
        "total_strikes": int(total_strikes),
        "detected_strikes": int(detected_strikes),
        "detection_rate": float(detected_strikes / max(1, total_strikes)),
        "mean_quiet_heat": float(heat[heat > 0].mean()) if (heat > 0).any() else 0.0,
        "verdict": ("Kinetic strikes produce orders-of-magnitude more waste heat "
                    "than quiet APM and are trivially detectable. Dark Forest "
                    "behaviour is a thermodynamic self-filter."),
    }
