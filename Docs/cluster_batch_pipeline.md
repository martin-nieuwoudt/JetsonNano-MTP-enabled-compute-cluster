# Cluster Batch Task — Regulatory-Document Intelligence Pipeline

> **Status:** Proposed (2026-07-13). Awaiting cluster bring-up (Phase 9c/9d) + Phase 9a stress test before implementation.
> **Origin:** Philosophical question — "what batch task suits this cluster?" — answered from the measured hardware profile, not from wishful thinking.

---

## 1. The core insight: what this cluster *is*

The defining trait is **asymmetric throughput**. The cluster is the computational *opposite* of a GPU server.

| Property | Value | Consequence |
|---|---|---|
| Model capacity | holds **70B** (35 GB) | 70B *quality* — a single Nano or most consumer GPUs can't do this |
| Generation speed | est. **5–15 tok/s** (spec-only, unmeasured) | far too slow for interactive chat |
| Nodes | 11 × weak (472 GFLOPS fp16 each) | embarrassingly parallel |
| Network | 1 Gbps, ~70 MB/s SCP | fine for fan-out, not for per-token streaming |

**Conclusion:** the cluster is **slow but can hold the model**. A server is fast *and* holds the model. This single asymmetry dictates the entire workload design space.

### FOR / NOT FOR

- **NOT for:** interactive chat (you'd watch 5 tok/s), real-time serving, anything latency-sensitive, high-QPS.
- **FOR:** work that exploits *capacity* (70B reasoning, 8192-ctx long docs) while *tolerating* the slow speed — i.e. **high-volume, high-value-per-token, latency-tolerant, partitionable** work.

**One-liner:** this cluster is a **"slow but wise" batch brain**. Give it the kind of work a human analyst does slowly over a library — read, extract, classify, summarize — at machine consistency and scale.

---

## 1.5 Scope clarification — what corpus, exactly?

> **This addresses a fair challenge:** the platform's purpose is *device management*, and almost no device data has been entered yet. So what would the model actually read?

**The pipeline does NOT process device records** (there are none yet) and is NOT an "audit" of the live system. It processes the **regulatory reference / source library** — the standards, HTA/HTM reference docs, and ISO material that already exists and is being curated (the `shared_base_docs` / Regs / ISO folders).

Two distinct corpora, two distinct pipelines:

| Pipeline | Input exists today? | Output |
|---|---|---|
| **A. Reference-index** (proposed now) | YES — the regulatory source library | structured metadata/index over the *knowledge base* the device system will consult |
| **B. Device-record** (future) | NO — devices not entered yet | structured assessment records per device |

Pipeline A is valuable *now* and aligns with the standing preference to build index/catalog layers over regulatory source folders before further work. It pre-builds the structured knowledge layer; when devices are later entered, Pipeline B can consult it. The "data represents devices, not software" invariant applies to Pipeline B (device records), **not** to A (reference docs).

**Pre-condition for A:** the source docs must be in machine-readable text. If they are still scanned PDFs, step one is text extraction (see `Docs/_extract_pdfs.py`) before any LLM pass.

---

## 2. Recommended task

**A batch regulatory-document intelligence pipeline over the regulatory *reference / source library*** — the standards, HTA/HTM reference docs, and ISO material (NOT device records; see §1.5).

For each document in the library, the 70B model:

1. **Extracts structured metadata** — jurisdiction, device class, standard references, effective dates, obligations.
2. **Writes a structured summary.**
3. **Assigns a classification.**

→ Output as **JSONL/CSV** that forms a structured **knowledge/index layer over the regulatory reference library** (see §1.5 — this is NOT device records; it is the source material the device system will later consult).

### Why it fits the compute profile exactly

- **Embarrassingly parallel** — one document = one independent RPC job; 11 nodes chew 11 at once.
- **Latency-tolerant** — overnight is fine. At ~10 tok/s × ~500 out-tokens/doc ≈ 50 s/doc → ~11/min → ~15k docs/weekend.
- **Benefits from 70B** — extraction/classification quality is where the big model earns its keep; a 7B would mangle the nuance.
- **Uses the long context** — regs are long; 8192 ctx matters here.
- **Directly serves the domain** — the work plan already lists Qwen 72B (coding) and Llama 70B (reasoning) as the target models.

---

## 2.5 Refinement (2026-07-13): standards-coverage gap analysis

> Proposed by user. Strictly stronger than the pure-index idea in §2 — and it *resolves* the §1.5 concern rather than re-raising it.

Instead of only *indexing* the reference library, the pipeline **reads the ISO/standard texts and evaluates how well the rules already encoded in the system represent those standards** — then finds gaps and proposes improvements.

- **Input A:** the ISO / HTA_HTM reference standards (the *rulebook*).
- **Input B:** the rules currently encoded in the system — the **cartridges** in `config/cartridges` (the deterministic logical rules). These are the "rules in the system" and can exist independently of any device records. So this audits *rule coverage*, **not** device data (resolving §1.5: legitimate even with zero devices entered).
- **Output:** per-standard gap report — `(standard clause → covering system rule? → if missing, suggested cartridge rule YAML)` — i.e. actionable improvement suggestions, not just an index.

### Why this is better than pure indexing
- **Actionable.** Indexing yields a catalog; gap analysis yields a *to-do list* for improving the system's rules.
- **Exploits 70B + 8192 ctx.** It is a *comparative* task: the model must hold BOTH the standard and the system rules in context and reason about the delta — the reasoning-long-context niche.
- **Closes the loop with existing tooling.** The output (suggested missing rules as YAML) is precisely what the `blind-spot-agent` ingests to extend cartridges. The cluster becomes the *generator* of cartridge-improvement proposals.
- **Latency-tolerant batch** — unchanged from §2, still a perfect fit.

### Honest precondition
The system's rules (cartridges) must be in a machine-readable form the model can read and compare. If they are sparse, the legitimate finding is "thin/partial coverage" — still valid and useful, just less nuanced than a mature baseline would produce.

### Prompt design — adapting the anti-hallucination system prompt

The user's standing `System Prompt.md` is the anti-hallucination base. It maps cleanly onto this task, but it is written for **one interactive analytical reply**, not a 15k-doc batch on a 5–15 tok/s cluster. Adaptation plan:

**Keep verbatim (prime anti-hallucination for gap analysis):**
- *"I don't know" > fabrication* — prime directive.
- *Distinguish "is" (fact) vs "may be" (hypothesis)* → maps to `COVERED` vs `PARTIAL`.
- *"DATA ABSENT" for gaps* → the natural label for "no cartridge addresses this clause."

**Adapt / strip for batch:**
- **Drop the header/footer protocol** (Motive Disclosure → Dialectical Synthesis → Verification Block). Forcing it per doc = token waste + slow throughput. Replace with a **terse per-doc JSONL schema**.
- **Disable the Synthesis Trigger** ("output only when told") — batch needs automatic per-doc emission.
- **Efficiency > Completeness** for batch — structured fields, not unabridged prose.
- **"Verify via tools / web search" is impossible on the cluster.** The Jetson `rpc-server` has **no tools, no function-calling, no web**. The model reasons only over the two provided inputs (standard text + cartridges). Rule becomes: *verify only against the provided cartridge set; every claim must cite a clause id + rule id from the inputs.*

**Add (cartridge-aware, critical for this task):**
- **Coverage citation rule:** a clause is `COVERED` *only* if the model cites the **exact cartridge rule id** + the clause it maps to. Otherwise `UNCOVERED` / `DATA ABSENT` with a proposed rule.
- **Per-clause confidence score** (0–100%) — the original scores globally; make it per-clause, since some clauses are ambiguous.
### Where each part lives: embed ONCE vs per-doc (decision)

The user's `System Prompt.md` is **partially** generic. Verdict:

**Embed ONCE as the global llama.cpp system prompt** — the task-agnostic anti-hallucination spine (§1 Core Mandate + §2 Data Handling backbone):
- *"I don't know" > fabrication*
- *Efficiency / density > volume / zero fluff*
- *Distinguish "is" (fact) vs "may be" (hypothesis)*
- *"DATA ABSENT" for gaps*
- *Stop and ask if ambiguous/unsure*

**Do NOT embed globally** — these clauses contradict the batch task and must be overridden per-doc (or dropped):
1. **"Verify via all available tools (incl. web search)"** — *impossible* on the cluster (rpc-server has no tools/web). Left global, the model either fails or hallucinates "verified." Override per-doc: *verify only against the provided cartridge set.*
2. **Synthesis Trigger** ("output only when told") — contradicts batch auto-emission. Drop globally.
3. **Header/footer protocol** (Motive → Dialectical Synthesis → Verification Block) — task-specific output structure, not a generic mandate. Belongs per-doc, and even there stripped to the JSONL schema.

**Put per-doc in the user turn:** the coverage-citation rule (gap-analysis-specific, the real anti-hallucination enforcement), the clause-by-clause mapping instruction, and the JSONL schema.

> Net: a cleaned generic core embedded once (cheap, stable across 15k docs) + task-specific guardrails per doc. The coverage-citation rule is the hard guard and must be per-doc, not global.
### Per-doc JSONL schema (proposed)
```json
{
  "doc_id": "ISO-XXXX-clause-set",
  "source_path": "...",
  "clauses": [
    {
      "clause_ref": "4.2.1",
      "normative_text": "...",
      "coverage": "COVERED | PARTIAL | UNCOVERED | DATA_ABSENT",
      "covering_rule_id": "cartridge:rule-id | null",
      "confidence": 0-100,
      "proposed_rule_yaml": "null | '<cartridge-ready YAML>'"
    }
  ],
  "model": "llama-3.3-70b-iq3_xs",
  "ts": "ISO-8601"
}
```

### Design trap (still applies)
This is a *faithful comparison*, not free-form summarization. The model must **not** hallucinate coverage. The coverage-citation rule above is the hard guard: no rule id cited → cannot be `COVERED`.

---

## 3. Alternative shapes (same profile)

- **Synthetic Q&A / training-data generation** from the corpus (feeds a future fine-tune).
- **RAG index build** — embeddings + extracted triples, not just vectors.
- **Cross-document obligation diffing** — "what changed between ISO edition X and Y" (needs long ctx + reasoning).

---

## 4. Honest caveat

The **5–15 tok/s is spec-only, not measured** (flagged in `cluster_hardware.md`). The real number must come from the **Phase 9a stress test** before we trust any throughput estimate. But the *shape* of the recommendation (batch, parallel, latency-tolerant) holds regardless of whether it's 5 or 15 tok/s.

---

## 5. Proposed implementation outline (to design next session)

> Not yet built. Outline only — to be fleshed out once the cluster is up.

- **Input:** corpus directory (PDFs / extracted text) on the Master PC or node0 NFS share.
- **Per-doc prompt template:** system + few-shot for metadata extraction → strict JSON schema.
- **Output schema (JSONL):** `{doc_id, source_path, jurisdiction, device_class, std_refs[], effective_date, obligations[], summary, classification, model, ts}`.
- **Fan-out:** `code/cluster_infer.py` submits one job per document across the 11 nodes (round-robin / queue), reusing the `--tensor-split 0.85,1,1,...` + QoS guards already in the canonical entry point.
- **Capture:** Phase 10.5 logged-run tier (`--log-file` + redirect → `.jsonl`).
- **Resilience:** failed doc → retry on next free node; dead node → watchdog (Phase 11) drops it from the RPC list.

---

## 6. Open questions for the design session

- Single model (Llama 70B reasoning) or route by doc type (Qwen 72B coding vs Llama 70B reasoning)?
- Extract-then-classify in one pass, or two passes (cheaper first pass to triage)?
- Where does the JSONL land — PC, or node0 NFS for the platform to ingest?
- Do we need a deterministic re-run key (doc hash) so re-runs are idempotent?
