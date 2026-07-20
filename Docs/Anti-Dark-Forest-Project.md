# Anti-Dark-Forest — Cluster Research Project

> **Purpose of this document:** Explain *what this project is, why it exists, and how the cluster is used to do it* — in the same spirit that `Nano Work Plan.md` explains the cluster build. This is the project-level map; the cluster build itself is covered by `Nano Work Plan.md`.

---

## 1. Motive

The Jetson Nano 11-node cluster was built as a general distributed-compute fabric. This project is the **first real workload we run on it** — a research programme around an *unpublished* theory tentatively titled **"Biology as Bounded Information"** (the *Anti-Dark Forest* thesis).

The thesis, in one sentence: **a civilisation that destroys or hides from others (the "Dark Forest" strategy) is thermodynamically and information-theoretically suboptimal compared with one that assimilates, simulates, and seeds.** The cluster lets us *simulate* the competing strategies at scale and then have a large model *judge* whether the mathematics actually supports the claim — and where it does not.

This is deliberately a **closed-loop research instrument**, not a one-shot script: small models on the cluster generate evidence, a large model defines the strategy and then critiques the result. The cluster is the lab; the theory is the specimen.

---

## 2. Terms & Theory Map

| Term | Meaning in this project |
|---|---|
| **Dark Forest** | Strategy of striking first / hiding to avoid detection (kinetic, zero-information). |
| **Synthetic / Assimilation** | Strategy of absorbing, simulating, and seeding others (high-information, low-entropy). |
| **EROI** | Energy Return On Investment of a strategy's compute yield. |
| **Heuristic Seeding** | Injecting external noise/structure to keep a system from stagnating as it expands. |
| **Bi-Modal Silence** | Outcome where efficient synthetic minds become practically invisible (Mode 2) — warfare phased out. |
| **KL-divergence** | Distance between "true" biology and a simulation of it; used to price the cost of destroying vs maintaining. |
| **Proposition (P1–P6)** | A discrete, testable claim the theory makes; each is mapped to one or more simulation methods. |
| **Critique Rule** | A known mathematical defect in a method (e.g. a hardcoded constant that bakes in the conclusion). |

The six propositions the judge evaluates (authoritative source: `code/allocator/judge_rubric.py`):

| ID | Proposition (short) | Method(s) |
|---|---|---|
| P1_EROI | Kinetic strike yields zero compute mass; assimilation compounds. | `marl`, `lean` |
| P2_HEURISTIC_SEEDING | Closed systems stagnate; external seeding is a prerequisite for mapping. | `montecarlo` |
| P3_THERMO_FILTER | Kinetic strikes are thermodynamically visible; synthetic APM is near-silent. | `thermo_ca` |
| P4_INFO_TRANSPARENCY | Simulating chaos costs more than maintaining it; destruction loses algorithmic entropy. | `kl_div` |
| P5_BAYES_BLINDNESS | Dark Forest blinds itself; thermodynamic actor reaches max info at a fraction of energy. | `bayesian` |
| P6_BI_MODAL_SILENCE | Synthetic minds become invisible; warfare is phased out. | `thermo_ca`, `lean` |

---

## 3. Architecture — The 3-Phase Meta-Loop

The project is a **three-phase loop** orchestrated by `code/allocator/orchestrator.py`. Compute is prioritised over Ethernet latency: heavy simulation runs *on-node*; only JSON results travel back over the wire.

```
        ┌──────────────────────────────────────────────────────────┐
        │                     LARGE MODEL                            │
        │  Phase 1: STRATEGY   →  DAG of tasks (capability, model)   │
        │  Phase 3: JUDGE      →  evaluate theory, critique math,    │
        │                          propose manuscript edits          │
        └───────────────┬───────────────────────────┬──────────────┘
                        │ plan (DAG)                 │ verdict + edits
                        ▼                            ▲
        ┌───────────────────────────────┐           │
        │   ORCHESTRATOR (node0 / PC)    │───────────┘
        │  scheduler + stage gates       │  Phase 2 results (JSON)
        └───────────────┬───────────────┘
                        │ dispatch (compute-on-node)
        ┌───────────────┴───────────────────────────────────────────┐
        │              SMALL MODELS — one per worker node            │
        │  Phase 2: EXECUTION via method harnesses (MCP tools)       │
        │  marl · montecarlo · thermo_ca · kl_div · lean · bayesian  │
        └───────────────────────────────────────────────────────────┘
```

### Phase 1 — Strategy (large model)
The large model produces a **directed acyclic graph of tasks**. Each task declares a `required_capability`, a `target_model` (large vs small), a `strategy_justification`, and its dependencies. This is the "plan" the cluster will execute.

### Phase 2 — Execution (small models, on-node)
Each worker node runs **one small model** that executes a task by calling a **method harness** (see §4). Compute happens *on the node*; only the JSON result dict returns over SSH/Ethernet. This is where latency is beaten by keeping the work local.

### Phase 3 — Judge (large model) — *the load-bearing phase*
All of Phase 1 + 2 converge here. A large model:
1. **Evaluates** the six propositions against the Phase-2 metrics (`judge.evaluate_propositions`),
2. **Critiques** the mathematics for circularities / malformed metrics (`judge.critique_methods`),
3. **Proposes** concrete manuscript edits ranked HIGH→LOW (`judge.propose_edits`),
4. **Blind-spot audit** — the generic "blind-spot agent" wired into Phase 3: cross-references the theory's enumerated claim-set (`THEORY_CLAIMS`, extracted from the unpublished manuscript) against propositions→methods, and reports three gap classes the other passes miss: **coverage gaps** (a claim the theory makes that no proposition tests), **evidence gaps** (a proposition covers it but produced no usable metric), and **orphan compute** (a method ran but supports no proposition). A non-zero gap count caps the stance at `PARTIAL` (`judge.blind_spot`),
5. **Aggregates** into a single stance: `REFUTED | INCONCLUSIVE | PARTIAL | SUPPORTED`.

Phase 3 is the most important phase: it is the only place the theory is actually *tested*, and it must surface where the simulations cheat (e.g. a hardcoded constant that pre-decides the answer) **and** where the theory itself asserts claims the simulations never examine.

---

## 4. Tool Surface — Method Harnesses (MCP)

Six pure-numpy simulation harnesses live in `code/methods/`. Each exposes `describe()`, `default_params()`, and `run(**params) -> dict` (the dict is tagged with `_method`). They are exposed to the agents as MCP tools on the cluster server (`code/mcp/cluster_mcp_server.py`):

| MCP tool | Purpose |
|---|---|
| `cluster.method.list` | List the 6 methods + one-line purpose. |
| `cluster.method.run(method, node_ip="", overrides="", timeout_s=120)` | Run a method. If `node_ip` is set, runs **on that node** over SSH (compute stays local); else runs locally. |
| `cluster.method.push` | SCP the `methods/` dir to every node's `REMOTE_METHODS_DIR` (`/home/jetson/methods`). |

| Method | What it simulates | Known critique (see `judge_rubric.py`) |
|---|---|---|
| `marl` | Multi-agent resource game; Dark Forest vs synthetic EROI. | **HIGH** — `dark_forest_EROI` hardcoded 0; win test `* 0.0` always False. |
| `montecarlo` | Cosmic ergodicity / stagnation under expansion. | LOW — fixed `r_proc`; expansion-vs-processing race implicit. |
| `thermo_ca` | Thermodynamic cellular automata; strike visibility. | MED — `detection_rate` numerator/denominator mismatched. |
| `kl_div` | KL cost of simulating vs maintaining biology. | **HIGH** — `cost_ratio` is a constant (1.0/0.01=100), not derived. |
| `lean` | Lean system dynamics; war vs assimilation supply chains. | **HIGH** — `war_yield` hardcoded 0.0 → warfare always loses (circular). |
| `bayesian` | Epistemic game; Dark Forest blindness vs thermodynamic info. | MED — strikes 100% (strawman prior); info density counts only threats. |

> **Why this matters:** the judge's `CRITIQUE_RULES` encode exactly these defects so Phase 3 *automatically* flags them. The current end-to-end run yields **stance = PARTIAL (4/6 propositions pass), 3 HIGH-severity circularities open** — i.e. the theory is *not yet* supported until those constants are replaced with real sweeps.

---

## 5. Model Mapping

| Role | Model size | Where it runs | Phase |
|---|---|---|---|
| **Strategist / Judge** | Large | Master PC (or node0) | 1 & 3 |
| **Executor** | Small | One per worker node (`.151`–`.160`) | 2 |

The orchestrator prioritises **compute locality**: Phase 2 work is dispatched to run where the data/CPU is, and only compact JSON results return. Ethernet latency is treated as the scarce resource; FLOPS are not.

---

## 6. Architectural Invariants (must not be violated)

These are carried over from the platform rules and apply to this project:

1. **Changeable logic is never hardcoded.** Proposition→method mappings, critique rules, and verdict thresholds live in **one** authoritative file: `code/allocator/judge_rubric.py`. They are *not* duplicated in `judge.py` or the orchestrator. If a proposition, threshold, or critique changes, it changes there.
2. **The judge must not trust the simulations blindly.** Any method that bakes in its conclusion (hardcoded constant, malformed metric) is a `CRITIQUE_RULE` and downgrades the verdict. A `PARTIAL`/`SUPPORTED` stance requires `high_severity_circularities_open == false`.
3. **Data represents simulation state, not software maturity.** The verdict's `pass_fraction`, proposition counts, and critique severities reflect the *actual* Phase-2 outputs — never a placeholder or a "how complete is the code" number.
4. **Compute over latency.** Phase 2 executes on-node; only JSON crosses the network.

---

## 7. File Map

| Path | Role |
|---|---|
| `code/methods/` | 6 simulation harnesses (`marl.py`, `montecarlo.py`, `thermo_ca.py`, `kl_div.py`, `lean.py`, `bayesian.py`) + `harness.py` (runner/registry). |
| `code/mcp/cluster_mcp_server.py` | FastMCP server exposing `cluster.method.*` tools. |
| `code/mcp/cluster_config.py` | `REMOTE_METHODS_DIR = /home/jetson/methods`. |
| `code/allocator/judge_rubric.py` | **Single source of truth** — `PROPOSITIONS` (P1–P11), `THEORY_CLAIMS` (enumerated manuscript claim-set for blind-spot audit), `CRITIQUE_RULES`, `VERDICT_THRESHOLDS`. |
| `code/allocator/judge.py` | Phase-3 judge: evaluate / critique / propose / aggregate / `judge_to_json`. |
| `code/allocator/orchestrator.py` | 3-phase meta-loop; `stage3_judge()` wired to the real judge. |
| `code/allocator/task_graph.py` | `Task` dataclass + `make_task()` / `affinity_key()`. |
| `code/allocator/scheduler.py` | `StageGateScheduler` — groups by affinity, drains, hot-swaps at group end. |

---

## 8. Status (2026-07-13, updated)

| # | Component | State |
|---|-----------|-------|
| 1 | 11 method harnesses (6 original + 5 Axis-B) | ✅ present, runnable via `harness.py` |
| 2 | MCP `cluster.method.*` tools | ✅ registered (list / run / push) |
| 3 | `judge_rubric.py` (source of truth) | ✅ created; P1–P11, 18 `THEORY_CLAIMS`, `CRITIQUE_RULES` (3 now `resolved`), `VERDICT_THRESHOLDS` |
| 4 | `judge.py` (Phase-3 engine) | ✅ created, **verified end-to-end** |
| 5 | Orchestrator `stage3_judge` wiring | ✅ replaced dry-run stub with real judge |
| 6 | End-to-end smoke test | ✅ runs; stance = **SUPPORTED** (9/11 pass), 0 HIGH circularities open |
| 7 | **Blind-spot pass** (`judge.blind_spot`) | ✅ built; 18/18 claims covered, 0 coverage gaps, 0 evidence gaps, 0 orphan compute |
| 8 | 3 HIGH circularities closed | ✅ `marl` / `lean` / `kl_div` now derive values from free params (salvage_fraction / war_yield / KL-proportional cost); rules flagged `resolved` |
| 9 | Cluster fleet (11 nodes) | ☐ 8/11 online (.150 WARN, .151–.157 PASS); workers 8–10 (.158–.160) still to flash — flashing in progress |

**Verdict detail (full 11-method judge run):**
- PASS: P1_EROI, P3_THERMO_FILTER, P4_INFO_TRANSPARENCY, P5_BAYES_BLINDNESS, P7_VIABILITY_KERNEL, P8_REPLICATION_THERMO, P9_TIEP_LIFETIME, P10_JEVONS_THROUGHPUT, P11_RECURSIVE_VIABILITY
- FAIL (genuine metric issues, not circularities): P2_HEURISTIC_SEEDING (`stagnation_reduction=0`), P6_BI_MODAL_SILENCE (`mean_quiet_heat=4.26`, needs <1.0)
- Remaining critique findings (non-blocking): MED `thermo_ca` (detection_rate malformed), MED `bayesian` (dark_prior strawman), LOW `montecarlo` (fixed r_proc)

**Next actions**
- Flash remaining workers (`.158`–`.160`) so Phase 2 can run distributed across all 11 nodes (target 11/11).
- Optionally fix P2 / P6 metric definitions (they are honest failures, not circularities — they do not block `SUPPORTED` at 0.82 pass fraction).
- Iterate the manuscript: feed `judge.propose_edits` + `blind_spots` output into the large model's Phase-3 prose pass.

---

## 9. How to Run (local smoke test)

```powershell
cd c:\Users\marti\Desktop\Cluster\code\allocator
& c:\Users\marti\Desktop\Cluster\.venv\Scripts\python.exe -c @"
import judge, sys
sys.path.insert(0, '../methods')
import harness
ms = ['marl','montecarlo','thermo_ca','kl_div','lean','bayesian']
res = [harness.run_method(m, {}) for m in ms]
print(judge.judge_to_json(res))
"@
```

This prints the full Phase-3 verdict: propositions (pass/fail + evidence), critique (severity-ranked), proposed edits, and the aggregate stance.
