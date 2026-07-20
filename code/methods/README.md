# Methods — Anti-Dark Forest simulation harnesses (Track 3)

Six falsifiable methodologies from `Tools for the small models.md`, each a
self-contained, runnable Python harness a small-model agent can execute and
iterate (the agent writes/repairs the script, runs it locally, reads output).

Each harness exposes a common interface via `harness.py`:
  - `run(**params) -> dict`  — executes the simulation, returns a result dict
  - `default_params() -> dict` — sensible starting parameters
  - `describe() -> str` — one-line purpose

The harnesses are PURE NUMPY (no torch/llama dependency) so they run on the
Jetson nodes or the PC identically. They are the *compute* layer; the small
models supply the *strategy* (which params to sweep) per the 3-stage loop.

## Exposed as agent tools (MCP)
Each method is callable by a small-model agent via the `cluster.method.*` tools
in `../mcp/cluster_mcp_server.py`:
  - `method_list()`            — list the 6 methods + purposes
  - `method_run(method, node_ip="", overrides="", timeout_s=120)`
                              — run a method; if `node_ip` is set the compute
                                happens ON-NODE (only the JSON result crosses
                                the 1GbE link), else it runs locally on the PC
  - `method_push()`            — SCP this dir to every node (REMOTE_METHODS_DIR)
                                so agents can run simulations locally on-node

This is the Stage-2 tool surface: the big model's strategy (Stage 1) assigns a
method to each small-model agent, which calls `method_run` to execute it. Lean
= Method 5 (cosmic supply-chain optimisation: warfare as Muda).

Methods:
  1. marl.py        — Asymmetric MARL: EROI of kinetic strike vs assimilation
  2. montecarlo.py  — Cosmic ergodicity: is Heuristic Seeding a prerequisite?
  3. thermo_ca.py   — 3D cellular automata: Dark Forest = thermal visibility filter
  4. kl_div.py      — Information theory: simulate bio-chaos vs harvest it (KL-div)
  5. lean.py        — System dynamics: warfare as Muda, phased out by assimilation
  6. bayesian.py    — Epistemic game theory: blindness vs transparency
