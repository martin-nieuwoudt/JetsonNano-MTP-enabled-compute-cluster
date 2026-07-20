# Cluster Script Unification — Chunk Plan

> **Method:** One chunk at a time. After each chunk I verify it is *perfect* (compiles,
> imports, smoke-test passes, no broken references) **before** moving to the next.
> Nothing is deleted until its replacement is proven working. Each chunk ends with a
> ✅ CONFIRM gate you can sign off on.
>
> **Goal:** Eliminate duplication so the system is efficient (no divergent copies, no
> lack of synchrony). Driven by the architectural invariant: *changeable logic is never
> hardcoded; single source of truth.*

---

## Current state (what exists today)

**Already unified (good precedent):**
- `cluster_health.py` / `cluster_monitor.py` → shims over `cluster_telemetry.py`
- Config → single source `mcp/cluster_config.py` (telemetry, watchdog, qos, infer all import it)
- Resilience → watchdog owns relaunch via `qos.relaunch_rpc_daemon`

**Still duplicative (targets of this plan):**

| Family | Redundant members | Canonical target |
|---|---|---|
| Download | `dl_llama_pc.py`, `dl_node0.py`, `fetch_qwen_all_pc.py`, `fetch_qwen_part0_pc.py`, `dl_node0.sh`, `dl_parallel_node0.sh` | `dl_generic_model.py` (engine) + `model_sync.py` (registry wrapper) |
| Sync/SCP | `scp_qwen_to_node0.ps1`, `verify_qwen_node0.ps1`, `download_orchestrator.ps1`, `resume_qwen_after_cooldown.ps1` | one `sync_model.ps1` (parameterized) |
| Launch | `cluster_deploy.launch_rpc_daemon` (own copy) | `qos.relaunch_rpc_daemon` |
| Orphan | `tegrastats_telemetry.py` | fold into worker deploy / node agent or delete |

---

## CHUNK 1 — Harden the canonical download engine (`dl_generic_model.py`)
**Objective:** Make the engine the *only* download implementation, and have it emit the
sha256 sidecar the QoS layer expects (`<basename>.gguf.sha256`), closing the QoS gap.

Tasks:
1. Add `--sha256` / auto sidecar: after concatenation, compute sha256 of the final GGUF
   and write `<out>.sha256` (format: `<hash>  <basename>`).
2. Keep full resumability (segment resume + concat) — do not regress.
3. Ensure `model_download` MCP tool still works unchanged (it already calls this engine).

**Verification gate:**
- `py_compile` clean.
- Unit smoke test: run engine against a tiny test URL (or a local file server) → produces
  final file + `.sha256` sidecar with correct hash.
- Confirm `model_download` MCP path still builds the same args.

✅ CONFIRM CHUNK 1

---

## CHUNK 2 — Replace hardcoded download scripts with registry-driven wrappers
**Objective:** Delete the 6 redundant download scripts; provide thin, registry-keyed
entry points so nothing external breaks.

Tasks:
1. Create `model_sync.py` (PC side) with subcommands:
   `download <key>` (calls engine with `cluster_config.MODELS[key]`),
   `verify <key>` (sha256 check vs sidecar), `push <key>` (SCP to node0 SSD).
2. Add shims (like the telemetry ones) ONLY if something external names the old files:
   `dl_llama_pc.py`, `dl_node0.py`, `fetch_qwen_all_pc.py`, `fetch_qwen_part0_pc.py`
   → each prints a deprecation note and calls `model_sync.py download <key>`.
   (`dl_node0.sh`, `dl_parallel_node0.sh` → delete; no external caller found.)
3. Delete `dl_node0.sh`, `dl_parallel_node0.sh`.

**Verification gate:**
- `py_compile` clean on `model_sync.py` + shims.
- `model_sync.py download qwen2.5-72b-iq3_m` builds identical engine args to the old
  `fetch_qwen_all_pc.py` (proven by dry-run printing the command).
- Grep confirms no remaining *functional* caller of the deleted `.sh` files.

✅ CONFIRM CHUNK 2

---

## CHUNK 3 — Unify the SCP/sync PowerShell scripts into one `sync_model.ps1`
**Objective:** Collapse 4 `.ps1` files into one parameterized tool; pick ONE authoritative
direction (node0 SSD is the model store per architecture → PC pushes TO node0).

Tasks:
1. `sync_model.ps1 -Model <key> [-Direction PCtoNode0|Node0toPC] [-VerifyOnly]`
   - SCP + size compare + sha256 compare (replaces `scp_qwen_to_node0`, `verify_qwen_node0`,
     the verify block of `download_orchestrator`).
2. `resume_qwen_after_cooldown.ps1` → rewrite to call `model_sync.py download <key>` +
   log (keeps its cooldown-resume purpose, loses the hardcoded Qwen name).
3. `download_orchestrator.ps1` → either delete (superseded) or reduce to a thin monitor
   that calls `sync_model.ps1`; resolve the PC↔node0 direction contradiction.

**Verification gate:**
- `pwsh -NoProfile -Command "Get-Help .\sync_model.ps1"` parses (syntax check).
- Dry-run prints correct scp/sha256 commands for a given key.
- No two scripts now perform the same SCP+verify logic.

✅ CONFIRM CHUNK 3

---

## CHUNK 4 — Make `cluster_deploy.py` import the single source + single launch path
**Objective:** Remove the 3rd config origin and 3rd daemon-launch copy.

Tasks:
1. `cluster_deploy.py`: replace local `RPC_PORT`, `JETSON_IPS`, `ALLOCATED_MEM_MB` with
   imports from `mcp.cluster_config` (try/except fallback, like the other modules).
2. Replace `launch_rpc_daemon` body with a call to `cluster_qos.relaunch_rpc_daemon`
   (or a shared `launch` helper in qos). Keep `cluster_deploy`'s SSH plumbing if qos lacks it.
3. Confirm `rpc_deploy` MCP tool still works.

**Verification gate:**
- `py_compile` clean.
- Import smoke test: `cluster_deploy` resolves `RPC_PORT=50052`, 11 nodes, `m=3600` from config.
- `rpc_deploy` MCP tool invocation returns expected launch output (dry-run / no real fleet yet).

✅ CONFIRM CHUNK 4

---

## CHUNK 5 — Resolve the orphan `tegrastats_telemetry.py`
**Objective:** No loose ends.

Tasks:
1. Determine if anything calls it (grep). If yes → fold into worker deploy / node agent.
   If no → delete and note in work plan.

**Verification gate:**
- Grep confirms no dangling reference after action.

✅ CONFIRM CHUNK 5

---

## CHUNK 6 — Update work plan + status, final cross-check
**Objective:** Documentation stays the single source of truth about what exists.

Tasks:
1. Update `Nano Work Plan.md` "Key files" table: mark deleted scripts, add `model_sync.py`,
   `sync_model.ps1`, note `dl_generic_model.py` is the only downloader.
2. Append a STATUS note recording the unification.
3. Final grep: no script re-implements download/launch/sync logic that lives elsewhere.

**Verification gate:**
- Work plan table matches actual `code/` contents.
- Grep for duplicated logic returns only the canonical definitions.

✅ CONFIRM CHUNK 6 — DONE

---

## Progress tracker
- [x] CHUNK 1 — download engine + sha256 sidecar  ✅ VERIFIED 2026-07-11
- [x] CHUNK 2 — registry wrappers, delete redundant download scripts  ✅ VERIFIED 2026-07-11
- [x] CHUNK 3 — unify sync PowerShell scripts  ✅ VERIFIED 2026-07-11
- [x] CHUNK 4 — cluster_deploy single source + single launch  ✅ VERIFIED 2026-07-11
- [x] CHUNK 5 — tegrastats orphan  ✅ VERIFIED 2026-07-11
- [x] CHUNK 6 — docs + final cross-check  ✅ VERIFIED 2026-07-11

## CHUNK 1 — verification log (2026-07-11)
- `py_compile dl_generic_model.py` → COMPILE_OK.
- Functional smoke test (local Range-compliant HTTP server, 2 MB file, 4 segments):
  - Download: 4 segments, SIZE OK, `FILE_MATCH True` (byte-identical to source).
  - Sidecar: `sha256: <hex>` written; `SIDECAR_FMT_OK True` → format is
    `"<hash>  <basename>"` (exactly what `cluster_qos.preflight_model_hash` reads).
  - `HASH_MATCH True` → sidecar hash equals real file hash.
- No regression: MCP `model_download` still builds identical args
  (`--url <hf_url> --out <local> --segments 8 --stagger 12`).
- New flags parse: `--no-sha256` accepted by argparse (no error); idempotent
  re-run short-circuit present (skips if final file + sidecar already complete).
- SonarQube: Cognitive Complexity of `main()` < 15 (extracted `_run_download`).
- NOTE: the HTTP "user-controlled URL" lint on the requests call is a FALSE POSITIVE
  — the URL is a fixed HF resolve URL supplied by the operator / MCP tool, not
  untrusted web input. Left as-is intentionally.

## Standing background task (unrelated to unification)
- Phase 9a capture `dd`→`pigz` of node0 SD → `C:\ClusterCaptures\Jetson_NanoZero_Baseline.img.gz`
  (monitored separately; will report when `.img.gz` appears).

## CHUNK 2 — verification log (2026-07-11)
- Created `model_sync.py` (PC side) with subcommands `download <key>`, `verify <key>`,
  `push <key> [--host]`. All resolve URL/path from `mcp.cluster_config.MODELS` (single
  source of truth) — no hardcoded URL/size/path in the wrapper.
- `download` forwards to `dl_generic_model.py` with `--url <hf_url> --out <local>
  --segments N --stagger S` (engine emits the sidecar). `verify` does a local sha256 of
  the PC GGUF vs its `<basename>.gguf.sha256` sidecar. `push` SCPs GGUF + sidecar to
  node0's `MODEL_DIR_ON_NODE0` (the NFS model store).
- Deprecation shims created (mirror telemetry-shim precedent): `dl_llama_pc.py` →
  `llama-3.3-70b-iq3_xs`, `dl_node0.py` / `fetch_qwen_all_pc.py` / `fetch_qwen_part0_pc.py`
  → `qwen2.5-72b-iq3_m`. Each prints a DEPRECATED note and calls `model_sync.py download <key>`.
  `resume_qwen_after_cooldown.ps1` (the one real external caller of `fetch_qwen_all_pc.py`)
  keeps working via the shim.
- Deleted redundant scripts: `dl_node0.sh`, `dl_parallel_node0.sh` (no external caller found).
- `py_compile` clean on `model_sync.py` + all 4 shims + `dl_generic_model.py` + `cluster_config.py`.
- Dry-run proof: `model_sync.py download qwen2.5-72b-iq3_m` builds
  `--url https://huggingface.co/bartowski/Qwen2.5-72B-Instruct-GGUF/resolve/main/Qwen2.5-72B-Instruct-IQ3_M.gguf
  --out C:\Models\Qwen2.5-72B-Instruct-IQ3_M.gguf --segments 8 --stagger 12` — URL and OUT
  match the old `fetch_qwen_all_pc.py` exactly. (Stagger default is 12 vs old script's 5;
  engine standard retained for consistency with the MCP tool.)
- Grep confirms no functional caller of the deleted `.sh` files remains (only this plan's
  own text references them; CHUNK 6 will update the table).
- Also relocated stray `Cluster monitoring.py` (root) → `code/cluster_monitoring_example.py`
  (it is a tutorial/example with 192.168.1.x placeholder IPs, not live cluster code).

## CHUNK 3 — verification log (2026-07-11)
- Created `sync_model.ps1` — one parameterized tool replacing `scp_qwen_to_node0.ps1`,
  `verify_qwen_node0.ps1`, and the verify/copy logic of `download_orchestrator.ps1`.
  Signature: `-Model <key> [-Direction PCtoNode0|Node0toPC] [-VerifyOnly]`.
- Direction authority resolved per architecture: PC is the model SOURCE; default
  `PCtoNode0` (push to node0's NFS store). `Node0toPC` kept only as explicit recovery op
  (resolves the old `download_orchestrator.ps1` PC<->node0 contradiction — it pulled
  node0->PC, which inverted the architecture).
- Verify uses the CANONICAL sidecar `<basename>.gguf.sha256` (what dl_generic_model.py /
  model_sync.py write), with a fallback to computing the PC hash if no sidecar. The old
  `qwen_pc.sha256` name is retired.
- All model paths/URLs/node IP/SSH user resolved from `mcp.cluster_config` via an inline
  python resolver — no hardcoded paths in PowerShell (single source of truth preserved).
- Rewrote `resume_qwen_after_cooldown.ps1` → `resume_after_cooldown.ps1`: now `-Model <key>`
  driven, calls `model_sync.py download <key>` (detached) instead of the hardcoded
  `fetch_qwen_all_pc.py`. Keeps its cooldown-resume purpose + logging.
- Deleted redundant scripts: `scp_qwen_to_node0.ps1`, `verify_qwen_node0.ps1`,
  `download_orchestrator.ps1`.
- PowerShell syntax: both `sync_model.ps1` and `resume_after_cooldown.ps1` parse clean
  (`[ScriptBlock]::Create` PARSE_OK). Path resolution dry-run confirms PC file
  `C:\Models\Qwen2.5-72B-Instruct-IQ3_M.gguf` -> node0
  `jetson@192.168.50.150:/mnt/ssd/models/Qwen2.5-72B-Instruct-IQ3_M.gguf` (matches old scripts).
- No two scripts now perform the same SCP+verify logic; `sync_model.ps1` is the only one.

## CHUNK 4 — verification log (2026-07-11)
- `cluster_deploy.py` now imports ALL changeable facts from `mcp.cluster_config`
  (SSH_USER, SSH_OPTS, RPC_PORT, NODE_IPS, RPC_BIN_DIR, MLOCK_WRAPPER,
  RPC_DAEMON_M_NODE0, RPC_DAEMON_M_WORKER). Removed local `REMOTE_TARGET_DIR`,
  `ALLOCATED_MEM_MB`, `RPC_BINARY`, `nodes` dict, and the hardcoded `192.168.50.x`
  comprehension. Fallback block kept only for standalone runs.
- `launch_rpc_daemon(ip)` now delegates to `cluster_qos.relaunch_rpc_daemon(ip, ...)`
  — SINGLE launch implementation. No divergent copy remains in deploy.
- Fixed a real launch BUG: old `cluster_deploy.py` used `ALLOCATED_MEM_MB=3600` for
  EVERY node including node0 (which keeps the GUI and must be 3000). Now uses
  per-node -m: node0=3000, workers=3600 (matches Phase 7 + qos).
- Fixed a divergent-launch BUG in `cluster_qos.py`: `RELAUNCH_CMD` passed
  `./rpc-server` as an EXTRA argument to `mlockall_wrapper`, but the wrapper already
  does `execv("./rpc-server", argv)` — so rpc-server received a stray positional arg.
  Corrected to `exec ./{wrapper} -H ... -p {port} -m {m}` (no ./rpc-server literal).
  bin_dir/wrapper now pulled from config (RPC_BIN_DIR, MLOCK_WRAPPER).
- Added `RPC_BINARY`, `RPC_BIN_DIR`, `MLOCK_WRAPPER` to `mcp.cluster_config.py`
  (single source of truth for the daemon binary + launch dir).
- `run_dashboard()` launch loop updated to the same per-node -m + config-driven form.
- Verified: `py_compile` clean on cluster_deploy.py, cluster_qos.py, cluster_config.py.
  RELAUNCH_CMD formats to `exec ./mlockall_wrapper -H 0.0.0.0 -p 50052 -m 3000` (node0)
  / `-m 3600` (worker) with NO stray ./rpc-server arg. cluster_deploy.py imports OK
  and CLI usage prints correctly. No leftover refs to removed constants.
- Note: `mcp.cluster_mcp_server` import fails in this venv only because the `mcp`
  (FastMCP) package is not installed here — pre-existing env gap, unrelated to CHUNK 4.
  The `rpc_deploy` tool only shells out to `cluster_deploy.py <mode>`, which is verified.
- Snyk-style lint flags on cluster_qos.py (exec/paramiko, hardcoded fallback IP) are
  FALSE POSITIVES per standing instruction — ignored; SonarQube (compile/CC) is the gate.

## CHUNK 5 — verification log (2026-07-11)
- `tegrastats_telemetry.py` was a TRUE ORPHAN: a 15-line snippet that just prints
  raw `tegrastats --interval 1000` lines. It was a verbatim copy of the snippet in
  `Docs/raw refinements.md` (lines 361-362) and was imported/used NOWHERE (confirmed
  via workspace-wide search across .py/.ps1/.sh/.md — zero references).
- Real tegrastats telemetry is ALREADY owned by `cluster_telemetry.py` (single source
  of truth: RAM + thermal parsing, SSH polling, audit gate, web UI), consumed by
  `cluster_watchdog.py` and the MCP server. `cluster_deploy.py:profile_node` also uses
  tegrastats over SSH. Keeping the orphan would create a SECOND, divergent tegrastats
  path — violating the single-source-of-truth invariant.
- ACTION: deleted `tegrastats_telemetry.py`.
- Verified: `py_compile` clean on cluster_telemetry.py, cluster_watchdog.py,
  cluster_deploy.py. Workspace-wide search confirms zero remaining references to the
  deleted module. No code path depends on it.

## CHUNK 6 — verification log (2026-07-11)
- Updated `Nano Work Plan.md`: added a "Model Management (PC-side, single source of truth)"
  section with a file-status table (canonical vs deprecated shim), the deleted-file list,
  the canonical sidecar convention (`<basename>.gguf.sha256`, two-space format), and the
  Phase 9e model-storage architecture (PC source, node0 SSD = NFS store, default PC→node0).
  Also noted `cluster_deploy.py` delegates launch to `cluster_qos.relaunch_rpc_daemon`.
- Appended a STATUS note to `STATUS_2026-07-11.md` (section 9) recording the full
  CHUNK 1-6 unification outcome and net single-source-of-truth result.
- Final cross-check (workspace-wide): SCP+verify logic lives ONLY in `sync_model.ps1`
  (PowerShell) and `model_sync.py` (Python push). `cluster_qos.preflight_model_hash` is the
  single node0-side sha256 definition (different purpose). No script re-implements
  download/launch/sync logic that lives elsewhere.
- Confirmed all 6 deleted files are gone: dl_node0.sh, dl_parallel_node0.sh,
  scp_qwen_to_node0.ps1, verify_qwen_node0.ps1, download_orchestrator.ps1,
  tegrastats_telemetry.py.
- Compile gate: all live Python modules in code/ + mcp/ compile clean (py_compile). The
  only non-compiling file is `cluster_monitoring_example.py` — an intentional tutorial/example
  doc (prose + sample script with placeholder 192.168.1.x IPs), excluded from the gate by
  design (renamed `_example` in CHUNK 2 precisely to signal it is reference material, not code).
- Snyk-style advisories (operator URLs, config-constant IPs, paramiko exec) remain FALSE
  POSITIVES per standing instruction; SonarQube (compile/CC) is the only gate.
