# Ensemble Inference Design Spec (Cluster)

**Status:** Design for review — no code yet.
**Depends on:** size-based split guideline + random node selection (Section 1, the foundation).
**Combiner strategy (v1):** Self-consistency (most frequent / highest-logprob answer across models).

---

## 0. Problem being solved

1. **Small models are slowed by forced fan-out.** A ≤3 GB GGUF pushed across all 11 nodes pays 11 collective RPC round-trips per decode step for zero capacity benefit. It should run on the *minimum* node count that fits it.
2. **Deterministic node hammering.** Always using the same nodes (node0 first, then .151–.160) concentrates electronic/thermal wear. Node selection should be **random each run**.
3. **No concurrency.** Because every model grabs all 11 nodes, only one model can run at a time. With small models using few nodes, **disjoint node partitions** let several models run simultaneously and combine their answers.

Hard constraint: a node's `ggml-rpc-server` holds **one** model's shard in UMA RAM at a time. Two llama-server clients cannot share a node. Therefore concurrent models need **disjoint node sets** — which the size guideline makes feasible.

---

## 1. Foundation — size-based split + random node selection

### 1.1 Config additions (`mcp/cluster_config.py`, single source of truth)

```python
# Size-based split guideline: (max_model_bytes, node_count) tiers, evaluated in order.
# A model whose size is <= the tier's max uses that many nodes (equal split within
# the subset). Anything larger than the last tier uses all SHARD_COUNT nodes.
SPLIT_GUIDELINE = [
    (3   * 1024**3, 1),    # <= 3 GB   -> 1 node
    (6   * 1024**3, 2),    # <= 6 GB   -> 2 nodes
    (12  * 1024**3, 4),    # <= 12 GB  -> 4 nodes
    (24  * 1024**3, 8),    # <= 24 GB  -> 8 nodes
    # else -> SHARD_COUNT (11)
]
RANDOM_NODE_SELECTION = True        # pick subset nodes at random each run
EXCLUDE_NODE0_FROM_RANDOM = False   # node0 IS included — excluding wastes 1/11 of the fleet
NODE0_SPLIT_WEIGHT = 0.5            # node0 keeps the GUI -> less headroom -> smaller share
NODE_SELECTION_SEED = None         # None = fresh random each call; int = reproducible (debug)
```

### 1.2 Helper: `select_nodes_for_model(model_path)`

Returns `(rpc_list, tensor_split)` for the chosen subset.

```
size = filesize(model_path)
n = SHARD_COUNT
for (max_b, cnt) in SPLIT_GUIDELINE:
    if size <= max_b: n = cnt; break
if n >= SHARD_COUNT:
    chosen = NODE_IPS                       # all nodes, equal split (legacy behaviour)
    split = "1," * SHARD_COUNT
else:
    pool = list(NODE_IPS)                       # node0 INCLUDED (no wasted compute)
    rng = Random(NODE_SELECTION_SEED)        # None seed -> system entropy each call
    chosen = rng.sample(pool, n)
    # node0 gets a smaller weight (GUI headroom); others equal 1.
    split = ",".join(str(NODE0_SPLIT_WEIGHT) if ip == NODE0_IP else "1"
                        for ip in chosen)
rpc = ",".join(f"{ip}:{RPC_PORT}" for ip in chosen)
return rpc, split
```

- `--tensor-split` length **must** equal `--rpc` server count → guaranteed by construction.
- `TENSOR_SPLIT_DEFAULT` (all-`1` ×11) stays as the explicit-override default; the helper is used when no override is supplied.
- llama.cpp still respects per-node free RAM at load, so a randomly chosen node with low headroom auto-shrinks — same graceful behaviour as today, just on a random subset.

### 1.3 Wiring points

- `cluster_server.py::cmd_start` — when `args.tensor_split` is the default sentinel, call `select_nodes_for_model(args.model)` and use its `rpc`/`split` instead of the full fleet.
- `cluster_infer.py::run` — same substitution before `build_rpc_list` / `build_cmd`.

---

## 2. Ensemble concurrency (builds on Section 1)

### 2.1 Port pool

```python
SERVER_PORT_POOL = [8080, 8081, 8082, 8083, 8084, 8085, 8086, 8087, 8088, 8089, 8090]  # 11 slots — one per node, the hardware ceiling for <3GB models
ENSEMBLE_AUTO_STOP = False    # keep ensemble models resident after a run (user decision: instant follow-ups > freed RAM)
```

### 2.2 Disjoint partition assignment

`partition_ensemble(models)` → `list[(model, port, rpc, split)]`, guaranteeing no node overlap.

```
rng = Random(NODE_SELECTION_SEED)
remaining = list(NODE_IPS)   # node0 INCLUDED (no wasted compute)
# biggest models pick first (they need the most nodes)
for model in sorted(models, key=filesize, reverse=True):
    n = tier_for(model)                       # from SPLIT_GUIDELINE
    if n > len(remaining):
        raise EnsembleError("not enough free nodes for all models")
    pick = rng.sample(remaining, n)
    remaining = [ip for ip in remaining if ip not in pick]
    assign model -> next free port from SERVER_PORT_POOL, rpc=pick, split="1,"*n
```

If the pool is exhausted mid-assignment → fail fast with a clear "not enough nodes" error (no silent sharing — sharing would clobber shards).

### 2.3 Launcher

Extend `cluster_server.py` with an `ensemble-start` subcommand (or a dedicated `cluster_ensemble.py`):

```
ensemble-start --models "C:\Models\A.gguf,C:\Models\B.gguf,C:\Models\C.gguf" \
               --ctx-size 2048
```

- For each model: launch a detached `llama-server` on its assigned port + disjoint rpc subset (Section 2.2).
- Poll `/health` per instance; report which came up.
- `ensemble-stop` tears them all down (or `ENSEMBLE_AUTO_STOP` does it post-call).

### 2.4 HTTP API

`POST /api/ensemble`
```json
{ "prompt": "...",
  "models": ["C:\\Models\\A.gguf", "C:\\Models\\B.gguf"],
  "mode": "explicit",
  "tokens": 256, "strategy": "self-consistency" }
```

**Model selection is the primary control.** The caller chooses *which* models
participate — this is what guarantees variation and more interesting results
(different architectures / quants / training mixes disagree in useful ways).
Two selection modes:

- `"mode": "explicit"` (default) — `models` is the exact list the caller
  picked. No auto-substitution.
- `"mode": "random-subset"` — `models` is ignored; the orchestrator picks
  a random subset of `N` models from the `MODELS_DIR` registry (size-checked
  to fit the free-node budget) so each run varies even with no user input.
  `N` comes from `ENSEMBLE_RANDOM_N` (default 3).

Either way, **node placement is still randomised per model** (Section 1.2), so
the same model mix never hammers the same nodes twice.

Flow:
1. `partition_ensemble(models)` → disjoint random node sets + ports.
2. Ensure each model resident on its instance (launch if needed).
3. Fan out the prompt to every instance's `/completion` (parallel, no per-call timeout — batch use case).
4. Collect answers + per-model status.
5. **Self-consistency combine** (Section 3).
6. If `ENSEMBLE_AUTO_STOP`: eject all ensemble models, freeing nodes.

Response:
```json
{ "ok": true,
  "answer": "<combined>",
  "strategy": "self-consistency",
  "per_model": [
    {"model": "A.gguf", "port": 8080, "nodes": ["192.168.50.151", ...], "answer": "...", "status": "ok"},
    {"model": "B.gguf", "port": 8081, "nodes": ["192.168.50.154", ...], "answer": "...", "status": "ok"}
  ] }
```

### 2.5 Failure handling

| Case | Behaviour |
|------|-----------|
| One model's server fails to come up | Drop that model, continue with the rest; listed in `per_model[].status="error"`. |
| One model times out | Drop it, continue. |
| All models fail | Return `ok:false` with aggregate error. |
| Not enough free nodes for the set | Fail fast before launching anything. |
| A node dies mid-run | That model's call errors → dropped; others unaffected (disjoint). |

### 2.6 Dashboard UI — ensemble model picker

The single-model **Model Selector** dropdown already exists. Add an **Ensemble**
panel that makes multi-model selection first-class:

- A **multi-select list** of every GGUF in `MODELS_DIR` (reuses the existing
  `GET /api/models` registry), each row showing size + estimated node count
  (from `SPLIT_GUIDELINE`) so the user sees the node budget before launching.
- A **mode toggle**: `Explicit` (tick the boxes) vs `Random subset (N)`
  (spin box, default 3).
- A **Run ensemble** button → `POST /api/ensemble` with the chosen models.
- The result card shows the **combined answer** + an expandable `per_model[]`
  breakdown (which nodes each model landed on, its raw answer, its tok/s).

This keeps model choice in the UI (not just the API) and makes the variation
visible: the user can see *which* models disagreed and *where* each ran.

---

## 3. Self-consistency combiner (v1)

Goal: return the **most frequent / highest-logprob** answer across the N models.

1. **Extractable answers** (MCQ / label / number / short phrase): normalize each model's answer (trim, lowercase, strip punctuation, map synonyms via a small config map), tally frequencies, return the mode. Ties broken by highest mean `timings.predicted_per_second` or first arrival.
2. **Free-form text:** self-consistency has no natural "mode". v1 degrades gracefully:
   - Cluster the N answers by semantic similarity (reuse the **9998 embedding tier** — `EMBED_PORT` — to embed each answer, then nearest-centroid / greedy same-cluster merge).
   - Return the answer closest to the largest cluster's centroid as the representative, and include the cluster sizes in `per_model` for transparency.
   - If embedding tier is down, fall back to returning all answers + a note ("free-form: no single mode; see per_model").
3. **Confidence signal:** if a model emits a logprob/confidence, weight the tally by it (optional, model-dependent).

> Note: meta-synthesis (feed all answers to a combiner model) was considered but deferred — self-consistency is cheaper (no extra inference) and matches the user's selection. Can be added as a `strategy: "meta"` later without API changes.

---

## 4. Open questions — RESOLVED (2026-07-15)

1. **node0 in ensembles** — INCLUDED (decided: excluding wastes 1/11 of the fleet). It gets a smaller split weight (`NODE0_SPLIT_WEIGHT = 0.5`) since it keeps the GUI. ✅ resolved.
2. **Auto-stop default** — **KEEP RESIDENT** (`ENSEMBLE_AUTO_STOP = False`). User wants instant follow-up questions; models stay loaded on their node subsets until manually ejected. ✅ resolved.
3. **Port pool size** — **11 slots** (`SERVER_PORT_POOL = [8080..8090]`). The real concurrency limiter is the node budget (`partition_ensemble`), not the port pool; 11 = the hardware ceiling for <3GB models (one per node). ✅ resolved.
4. **Free-form clustering** — **BOTH**. Self-consistency for the final combined answer AND embedding-based clusters (9998 tier) shown as a side panel for the "which models agreed / outliers" view. ✅ resolved.
5. **Default ensemble mode** — **EXPLICIT SELECT** (user picks exactly which models via multi-select). Random-subset remains available as a non-default toggle. ✅ resolved.
6. **Max models per ensemble** — **CAP AT 11** (one per node). `partition_ensemble` enforces the true per-run node budget, so larger models auto-reduce concurrency. ✅ resolved.

---

## 5. Implementation order (once approved)

1. `cluster_config.py`: `SPLIT_GUIDELINE`, `RANDOM_NODE_SELECTION`, `EXCLUDE_NODE0_FROM_RANDOM`, `NODE_SELECTION_SEED`, `SERVER_PORT_POOL`, `ENSEMBLE_AUTO_STOP`.
2. `cluster_config.py`: `select_nodes_for_model()`, `tier_for()`, `partition_ensemble()`.
3. `cluster_server.py`: wire `select_nodes_for_model` into `cmd_start`; add `ensemble-start` / `ensemble-stop`.
4. `cluster_infer.py`: wire helper into `run()`.
5. `cluster_telemetry.py`: add `POST /api/ensemble` + self-consistency combiner; record per-model tok/s to metrics.
6. Restart dashboard, verify: small model → few random nodes; ensemble → disjoint random sets; combine returns mode.
