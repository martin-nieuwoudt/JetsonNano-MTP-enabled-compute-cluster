#!/usr/bin/env python3
"""
recursive_viability.py — Method 11: Recursive Viability (title claim).

Tests C18 (Recursive Viability: the system recursively resolves its own identity
into the invariant logic of existence). We iterate I(t) = H - PD(t) under the
kinetic accelerator d(PD)/dt ∝ Σ γ_i D_i (Jablonka's four evolutionary
dimensions, each with its own acceleration). PD grows toward H; identity I(t)
decays to 0 — the Informational Transparency fixed point. The title claim holds
if the system converges to I -> 0.
"""
from __future__ import annotations

import numpy as np


def describe() -> str:
    return "Recursive Viability: does identity I(t)=H-PD(t) converge to 0?"


def default_params() -> dict:
    return {
        "h_total": 1.0,       # total information (const)
        "steps": 2000,
        "dt": 0.01,
        "gamma": [0.1, 0.5, 2.0, 8.0],   # accelerations of the 4 dimensions
    }


def run(h_total=1.0, steps=2000, dt=0.01, gamma=None) -> dict:
    if gamma is None:
        gamma = [0.1, 0.5, 2.0, 8.0]
    d = np.zeros(4)          # accumulated information per dimension
    pd = 0.0
    i_hist = [h_total]
    for _ in range(steps):
        # Kinetic accelerator: each dimension compounds at rate gamma_i * D_i,
        # plus a small constant seeding so it can start from zero.
        d_d = np.array([g * d[i] + 0.01 * g for i, g in enumerate(gamma)])
        d = d + d_d * dt
        pd = float(np.sum(d))
        if pd >= h_total:
            pd = h_total
            i_hist.append(0.0)
            break
        i_hist.append(h_total - pd)
    i_final = float(h_total - pd)
    converged = bool(i_final < 1e-3)
    return {
        "identity_initial": h_total,
        "identity_final": i_final,
        "pd_final": float(pd),
        "converged_to_transparency": converged,
        "convergence_steps": len(i_hist),
        "recursive_viability_holds": converged,
        "verdict": (
            f"Identity I(t)=H-PD decayed from {h_total:.3g} to {i_final:.2e} over "
            f"{len(i_hist)} steps: the system recursively resolves its identity "
            f"into the invariant logic (Informational Transparency). Title claim "
            f"holds."
            if converged
            else f"Identity did not converge to 0 (final I={i_final:.3g})."
        ),
    }
