#!/usr/bin/env python3
"""
judge_rubric.py — SINGLE SOURCE OF TRUTH for Phase-3 judging.

Phase 3 is the load-bearing phase: all of Phase 1 (strategy) and Phase 2
(execution) converge on the large model, which must (a) evaluate the Anti-Dark
Forest theory against the empirical outputs, (b) critique the *mathematics* of
the harnesses, and (c) propose concrete manuscript improvements.

This module holds the changeable logic — the proposition->method map, the pass
conditions, the known mathematical weaknesses of each harness, and the verdict
thresholds. judge.py reads from here; nothing is hardcoded in the judge logic.
This satisfies the architectural invariant: "Changeable logic is never hardcoded."

All thresholds/conditions are data here, not code branches in judge.py.
"""
from __future__ import annotations

from typing import Dict, List

# ---------------------------------------------------------------------------
# THEORY PROPOSITIONS  (what the harnesses are supposed to test)
# Each proposition names the methods that test it, the metric keys to read from
# those methods' result JSON, and a pass condition expressed as a callable-free
# spec the judge evaluates. `pass` is a small dict the judge interprets:
#   {"metric": <key>, "op": "< | > | == | !=", "val": <number>}
# Multiple conditions are ANDed. `methods` lists the _method tags to pull.
# ---------------------------------------------------------------------------
PROPOSITIONS: List[Dict] = [
    {
        "id": "P1_EROI",
        "statement": ("Kinetic strike yields zero computational mass (EROI=0); "
                      "assimilation compounds. Dark Forest is thermodynamically "
                      "suboptimal."),
        "methods": ["marl", "lean"],
        "conditions": [
            {"metric": "dark_forest_EROI", "op": "==", "val": 0.0},
            {"metric": "synthetic_EROI_ratio", "op": ">", "val": 1.0},
        ],
        "notes": "MARL gives EROI; Lean gives the supply-chain dominance analogue.",
    },
    {
        "id": "P2_HEURISTIC_SEEDING",
        "statement": ("Closed synthetic systems stagnate as the universe expands; "
                      "Heuristic Seeding (external noise) is a mathematical "
                      "prerequisite for long-term universal mapping."),
        "methods": ["montecarlo"],
        "conditions": [
            {"metric": "closed_stagnation_rate", "op": ">", "val": 0.0},
            {"metric": "stagnation_reduction", "op": ">", "val": 0.0},
        ],
        "notes": "Monte Carlo of cosmic ergodicity.",
    },
    {
        "id": "P3_THERMO_FILTER",
        "statement": ("Dark Forest kinetic strikes are thermodynamically visible "
                      "(entropy spikes); synthetic APM is near-absolute-zero quiet. "
                      "Aggression self-filters."),
        "methods": ["thermo_ca"],
        "conditions": [
            {"metric": "detection_rate", "op": ">", "val": 0.5},
        ],
        "notes": "Thermodynamic cellular automata. detection_rate is now per-strike "
                 "(bounded [0,1]); P3 reads it directly.",
    },
    {
        "id": "P4_INFO_TRANSPARENCY",
        "statement": ("Simulating biological chaos costs more than maintaining the "
                      "incubator (KL>0, cost ratio >> 1). Destroying it is a "
                      "catastrophic loss of algorithmic entropy."),
        "methods": ["kl_div"],
        "conditions": [
            {"metric": "cost_ratio_sim_over_maintain", "op": ">", "val": 1.0},
        ],
        "notes": "KL-divergence. cost ratio is derived from the KL estimate "
                 "(resolved; see CRITIQUE_RULES).",
    },
    {
        "id": "P5_BAYES_BLINDNESS",
        "statement": ("Dark Forest blinds itself (high false-positive energy spend, "
                      "zero info gain); Thermodynamic actor reaches max information "
                      "density at a fraction of the energy."),
        "methods": ["bayesian"],
        "conditions": [
            {"metric": "energy_ratio_dark_over_thermo", "op": ">", "val": 1.0},
            {"metric": "thermo_info_density", "op": ">", "val": 0.0},
        ],
        "notes": "Epistemic game theory.",
    },
    {
        "id": "P6_BI_MODAL_SILENCE",
        "statement": ("Substrate Succession: synthetic minds consume energy so "
                      "efficiently they become practically invisible (Bi-Modal "
                      "Silence, Mode 2). Warfare is phased out."),
        "methods": ["thermo_ca", "lean"],
        "conditions": [
            {"metric": "mean_quiet_heat", "op": "<", "val": 1.0},
            {"metric": "assimilation_share", "op": ">", "val": 0.5},
        ],
        "notes": "Emergent from quiet-heat + assimilation dominance.",
    },
    {
        "id": "P7_VIABILITY_KERNEL",
        "statement": ("The Viability Kernel V = {w : E(w)=1} is a sparse, "
                      "low-dimensional subset of state space, and Bounded MaxEnt "
                      "yields a finite positive lethality multiplier lambda pricing "
                      "exit from V."),
        "methods": ["viability_kernel"],
        "conditions": [
            {"metric": "viability_fraction", "op": "<", "val": 0.5},
            {"metric": "effective_dimension", "op": "<", "val": 12.0},
            {"metric": "bounded_maxent_converged", "op": "==", "val": 1.0},
        ],
        "notes": "Axis B (intrinsic). Closes C1 + C11 coverage gap.",
    },
    {
        "id": "P8_REPLICATION_THERMO",
        "statement": ("Self-replication dissipates at least England's bound and "
                      "heat scales with copied complexity (complexity is "
                      "thermodynamically necessary)."),
        "methods": ["replication_thermo"],
        "conditions": [
            {"metric": "england_bound_holds", "op": "==", "val": 1.0},
        ],
        "notes": "Axis B (intrinsic). Closes C5 coverage gap.",
    },
    {
        "id": "P9_TIEP_LIFETIME",
        "statement": ("Life maximizes Time-Integrated Entropy Production (TIEP) at "
                      "lower peak rate and far longer lifetime than an explosion; "
                      "homeostasis is throttled entropy."),
        "methods": ["tiep_lifetime"],
        "conditions": [
            {"metric": "life_maximizes_tiep", "op": "==", "val": 1.0},
            {"metric": "lifetime_ratio", "op": ">", "val": 1.0},
        ],
        "notes": "Axis B (intrinsic). Closes C8 + C4 coverage gap.",
    },
    {
        "id": "P10_JEVONS_THROUGHPUT",
        "statement": ("Selection for individual metabolic efficiency raises total "
                      "population power throughput (Jevons paradox): local "
                      "efficiency -> global dissipation."),
        "methods": ["jevons_throughput"],
        "conditions": [
            {"metric": "jevons_effect", "op": "==", "val": 1.0},
        ],
        "notes": "Axis B (intrinsic). Closes C9 coverage gap.",
    },
    {
        "id": "P11_RECURSIVE_VIABILITY",
        "statement": ("Identity I(t)=H-PD(t) converges to 0 under the kinetic "
                      "accelerator: the system recursively resolves its identity "
                      "into the invariant logic (Informational Transparency)."),
        "methods": ["recursive_viability"],
        "conditions": [
            {"metric": "recursive_viability_holds", "op": "==", "val": 1.0},
        ],
        "notes": "Axis B (intrinsic). Closes C18 (title claim) coverage gap.",
    },
]

# ---------------------------------------------------------------------------
# THEORY CLAIMS  (the enumerated claim-set of "Biology as Bounded Information")
# Extracted from the unpublished manuscript (Draft 1 + supporting docs) so the
# judge can detect BLIND SPOTS: claims the theory makes that no proposition /
# method actually tests. This is the generic "blind-spot agent" logic wired
# into Phase 3 — it cross-references claims -> propositions -> methods.
# `covered_by` lists the proposition ids that should test the claim. An empty
# list = COVERAGE GAP (the theory asserts it, but nothing in Phase 2 checks it).
# `partial` flags claims only weakly touched by their covering propositions.
# Source sections refer to Draft 1 .tx files in the theory folder.
# ---------------------------------------------------------------------------
THEORY_CLAIMS: List[Dict] = [
    {
        "id": "C1_VIABILITY_KERNEL",
        "statement": ("Life is the inverse image of environmental constraint; the "
                      "Viability Kernel V is a sparse subset of state space where "
                      "persistence is possible (V = {w : E(w)=1})."),
        "section": "2b",
        "covered_by": ["P7_VIABILITY_KERNEL"],
    },
    {
        "id": "C2_FRACTAL_FILLING",
        "statement": ("Branching/tree structures are the optimal space-filling "
                      "solution; PD ∝ e^(H/D); phylogenetic diversity is the metric "
                      "of occupied phase space."),
        "section": "2b",
        "covered_by": ["P2_HEURISTIC_SEEDING"],
        "partial": True,
    },
    {
        "id": "C3_MEPP",
        "statement": ("Life self-organizes to maximize the rate of entropy "
                      "production (Maximum Entropy Production Principle)."),
        "section": "3",
        "covered_by": ["P1_EROI", "P3_THERMO_FILTER"],
        "partial": True,
    },
    {
        "id": "C4_DISSIPATIVE_STRUCTURES",
        "statement": ("Life is a class of dissipative structures that use "
                      "information (genetic memory) to stabilize the dissipation "
                      "channel against fluctuations."),
        "section": "3",
        "covered_by": ["P3_THERMO_FILTER"],
        "partial": True,
    },
    {
        "id": "C5_ENGLAND_LOWER_BOUND",
        "statement": ("Self-replication requires dissipation of a minimum heat "
                      "(England's bound); complexity is thermodynamically necessary, "
                      "not merely unlikely."),
        "section": "3",
        "covered_by": ["P8_REPLICATION_THERMO"],
    },
    {
        "id": "C6_ENERGY_RATE_DENSITY",
        "statement": ("Evolutionary advancement correlates with energy throughput "
                      "(Chaisson Phi_m ladder: galaxies->stars->planets->biosphere->"
                      "brains); arrow of evolution = arrow of dissipation."),
        "section": "3",
        "covered_by": ["P1_EROI"],
        "partial": True,
    },
    {
        "id": "C7_INFO_ENERGY_EQUIVALENCE",
        "statement": ("Information and energy are fungible (Landauer + Sagawa); "
                      "total thermodynamic capture Phi_total = Phi_energy + "
                      "Phi_information."),
        "section": "3",
        "covered_by": ["P4_INFO_TRANSPARENCY", "P5_BAYES_BLINDNESS"],
    },
    {
        "id": "C8_STABILITY_CONSTRAINT_TIEP",
        "statement": ("Life maximizes Time-Integrated Entropy Production, not "
                      "instantaneous rate; homeostasis is throttled entropy. This "
                      "distinguishes life from fire/explosion (tau_life -> 0)."),
        "section": "3",
        "covered_by": ["P9_TIEP_LIFETIME"],
    },
    {
        "id": "C9_JEVONS_PARADOX",
        "statement": ("Selection for individual metabolic efficiency drives "
                      "population-level total power throughput (Lotka); local "
                      "efficiency -> global dissipation via Jevons effect."),
        "section": "3",
        "covered_by": ["P10_JEVONS_THROUGHPUT"],
    },
    {
        "id": "C10_FREE_ENERGY_KL",
        "statement": ("Survival is inference: min variational Free Energy == min "
                      "D_KL(P || Q); high KL = surprise/death, low KL = predicted/"
                      "maintained life."),
        "section": "3",
        "covered_by": ["P4_INFO_TRANSPARENCY", "P5_BAYES_BLINDNESS"],
    },
    {
        "id": "C11_BOUNDED_MAXENT",
        "statement": ("Bounded MaxEnt: maximize internal entropy subject to the "
                      "viability constraint; lethality Lagrange multiplier lambda "
                      "prices exit from V."),
        "section": "3",
        "covered_by": ["P2_HEURISTIC_SEEDING"],
        "partial": True,
    },
    {
        "id": "C12_IDENTITY_DELTA",
        "statement": ("Identity I(t) = H(t) - PD(t); high I = 'loud' phase (slack/"
                      "redundancy), I->0 = 'silent' resolved phase."),
        "section": "5",
        "covered_by": ["P6_BI_MODAL_SILENCE"],
    },
    {
        "id": "C13_LANDAUER_TAX",
        "statement": ("Identity Tax Phi_tax ∝ k_B T · I(t); visibility (anomalous "
                      "heat/signal) is a direct measure of thermodynamic "
                      "inefficiency. Loud = high tax."),
        "section": "5",
        "covered_by": ["P3_THERMO_FILTER", "P6_BI_MODAL_SILENCE"],
    },
    {
        "id": "C14_TRANSPARENCY_LIMIT",
        "statement": ("Asymptotic limit: lim I(t)=0 => H ≡ PD; Informational "
                      "Transparency — maximal computation, minimal dissipation, "
                      "thermodynamically indistinguishable from background."),
        "section": "5",
        "covered_by": ["P6_BI_MODAL_SILENCE", "P3_THERMO_FILTER"],
    },
    {
        "id": "C15_BI_MODAL_SILENCE",
        "statement": ("Bi-Modal Distribution of Silence: Mode 1 (PD->0, "
                      "un-capitalized) and Mode 2 (PD=H, perfected logic) are "
                      "observationally identical; Fermi paradox = artifact."),
        "section": "6",
        "covered_by": ["P6_BI_MODAL_SILENCE", "P3_THERMO_FILTER"],
    },
    {
        "id": "C16_LOUD_TRANSIENT",
        "statement": ("The 'Loud Transient' (human condition): the H>PD intermediate "
                      "noisy phase between the two silent modes."),
        "section": "6",
        "covered_by": ["P6_BI_MODAL_SILENCE"],
        "partial": True,
    },
    {
        "id": "C17_KINETIC_ACCELERATION",
        "statement": ("Evolution is a kinetic accelerator driving PD->H convergence; "
                      "higher-order evolutionary dimensions (genetic->symbolic) "
                      "accelerate it."),
        "section": "1/4/7",
        "covered_by": ["P2_HEURISTIC_SEEDING"],
        "partial": True,
    },
    {
        "id": "C18_RECURSIVE_VIABILITY",
        "statement": ("Recursive Viability: the system recursively resolves its own "
                      "identity into the invariant logic of existence (title claim "
                      "of the theory)."),
        "section": "title",
        "covered_by": ["P11_RECURSIVE_VIABILITY"],
    },
]

# ---------------------------------------------------------------------------
# CRITIQUE RULES  (known mathematical weaknesses in the harnesses)
# Each rule is a finding the judge raises when the named method appears in the
# Phase-2 outputs. `severity`: HIGH = verdict-circular (conclusion baked in),
# MED = metric malformed, LOW = modeling simplification worth noting.
# `proposed_fix` is the concrete manuscript/code edit the judge proposes.
# ---------------------------------------------------------------------------
CRITIQUE_RULES: List[Dict] = [
    {
        "method": "marl",
        "severity": "HIGH",
        "resolved": True,
        "issue": ("dark_forest_EROI was hardcoded to 0.0 and dark_forest_win_rate "
                  "tested `syn_compute < df_e * 0.0` (always 0 -> always False). "
                  "RESOLVED: EROI is now derived from salvage_fraction; win condition "
                  "is df_net > syn_net; crossover_salvage_fraction reported."),
        "proposed_fix": ("Compute actual compute return from strikes (e.g. partial "
                         "salvage of vaporised mass) and make the win condition a "
                         "function of p_detect / counter_cap / weapon_travel. Report "
                         "the crossover where Dark Forest becomes rational."),
    },
    {
        "method": "lean",
        "severity": "HIGH",
        "resolved": True,
        "issue": ("war_yield was hardcoded to 0.0, so war_net = -war_cost was always "
                  "negative and assimilation won by construction. RESOLVED: war_yield "
                  "is a free parameter; warfare is chosen when war_net > assim_net; "
                  "crossover_war_yield reported."),
        "proposed_fix": ("Sweep war_yield (contested-resource salvage) as a free "
                         "parameter and report the efficiency-frontier crossover "
                         "where warfare becomes rational. Let the data, not the "
                         "constant, decide."),
    },
    {
        "method": "kl_div",
        "severity": "HIGH",
        "resolved": True,
        "issue": ("cost_ratio_sim_over_maintain was sim_compute_per_dim / "
                  "incubator_cost = 1.0 / 0.01 = 100, a CONSTANT independent of the "
                  "KL estimate. RESOLVED: sim cost is now proportional to KL "
                  "(sim_cost ∝ 1 + KL_true_vs_sim); ratio derived from the estimate."),
        "proposed_fix": ("Make simulation cost proportional to KL (sim_cost ∝ "
                         "KL_true_vs_sim) so the ratio is derived from the "
                         "distribution distance, not a fixed constant pair."),
    },
    {
        "method": "thermo_ca",
        "severity": "MED",
        "resolved": True,
        "issue": ("detection_rate = detected_heat_events / total_strikes. The "
                  "numerator accumulates over all steps (a cell can be recounted "
                  "many times) while the denominator is an event count, so the "
                  "metric is malformed and can exceed 1 or be meaningless. "
                  "RESOLVED: detection is now per-strike (the step a cell fires "
                  "kinetically, record whether its heat exceeded the threshold); "
                  "detection_rate = detected_strikes / total_strikes, bounded [0,1]."),
        "proposed_fix": ("Track per-strike detection: in the step a cell fires "
                         "kinetically, record whether its heat exceeded the "
                         "detection threshold. detection_rate = detected / fired."),
    },
    {
        "method": "bayesian",
        "severity": "MED",
        "resolved": True,
        "issue": ("Dark Forest is modeled as striking 100% of signals (dark_prior "
                  "> 0.5 is always true), a strawman that never varies the prior. "
                  "thermo_info_density only counts resolved threats, not correct "
                  "benign classifications. RESOLVED: dark_prior is now swept over "
                  "[0.5, 1.0]; false-positive rate measured vs threat_base_rate; "
                  "thermo_info_density = correct classifications / total signals "
                  "(threats + benign)."),
        "proposed_fix": ("Sweep dark_prior in [0.5, 1.0] and measure false-positive "
                         "rate vs threat_base_rate; report info density as "
                         "correct classifications / total signals (both threats and "
                         "benign)."),
    },
    {
        "method": "montecarlo",
        "severity": "LOW",
        "resolved": True,
        "issue": ("Stagnation is driven by a fixed r_proc < r_exp; seeding only "
                  "matters once model_health decays toward 0. The 'expanding "
                  "universe' framing implies processing capacity should scale, but "
                  "r_proc is constant. RESOLVED: r_proc now scales with model-health "
                  "recovery (proc_growth) so the expansion-vs-processing race is "
                  "explicit; closed=1.0, seeded=0.0214, reduction=0.9786."),
        "proposed_fix": ("Let r_proc scale with model_health recovery, or model "
                         "processing-capacity growth, so the expansion-vs-processing "
                         "race is explicit rather than implicit in decay."),
    },
]

# ---------------------------------------------------------------------------
# VERDICT THRESHOLDS  (how to aggregate proposition passes + critique into a
# final thesis stance). Data, not code, so the stance logic stays tunable.
# ---------------------------------------------------------------------------
VERDICT_THRESHOLDS = {
    # Fraction of propositions that must PASS (clean metric) to claim SUPPORTED.
    "supported_min_pass_frac": 0.66,
    # If any HIGH-severity circularity is uncorrected, cap the stance at PARTIAL
    # regardless of pass count (a circular proof cannot SUPPORT a thesis).
    "cap_at_partial_if_high_critique": True,
    # Stance labels, in order of strength.
    "stances": ["REFUTED", "INCONCLUSIVE", "PARTIAL", "SUPPORTED"],
}
