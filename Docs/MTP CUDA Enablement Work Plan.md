MTP CUDA Enablement — Work Plan

**Goal:** Build a CUDA-enabled `ggml-rpc-server` from the MTP source tree (`llama.cpp-mtp`, commit `20a04b2`) that compiles on Jetson Nano's CUDA 10.2 / C++14 toolchain and runs MTP models (Qwythos-9B-MTP-Q8_0, etc.) across the 11-node cluster.

**Status:** ✅ **COMPLETE** — Full 11-node MTP fleet deployed and operational (2026-07-20). The MTP CUDA port is built, validated, and running on all 11 nodes via dashboard at http://localhost:9090. **Live status doc:** `MTP_CUDA_STATUS.md`.

**Estimated total effort:** 2–3 days of focused work (completed).

---

## Progress Snapshot (2026-07-20 — COMPLETE)

| Item | State |
|---|---|
| Swarm mode | **STOPPED** — no active processes; last harness run was a no-op (brief not attached). All work was manual. |
| Phase 0 (non-MTP Qwythos v2 Q8_0) | Deferred — superseded by the CUDA port effort. |
| Phases A–D (C++17→C++14 port) | **DONE** — 2026-07-17 build compiled every CUDA TU. BF16 intrinsic shim (`__float2bfloat16`/`__bfloat162float`) resolved the last CUDA-11 blocker. |
| **Blocker #4** (`ggml-cuda.cu` `ggml_backend_cuda_interface`) | **FIX APPLIED** — struct gained `set_tensor_2d_async`/`get_tensor_2d_async`/`graph_optimize` fields the initializer lacked (shift-by-2). Added 3 `NULL` entries. |
| **Buffer interface desync** (newly discovered) | **FIX APPLIED** — both `ggml_backend_cuda_buffer_interface` and `ggml_backend_cuda_split_buffer_interface` updated: added `set_tensor_2d`/`get_tensor_2d` `NULL` fields; `init_tensor` return type changed to `enum ggml_status` with `GGML_STATUS_SUCCESS` returns; `cpy_tensor` return type changed to `bool` with proper returns. |
| **Return-type mismatches** (newly discovered) | **FIX APPLIED** — 3 `void` functions (`graph_optimize`×2, `unregister_host_buffer`) now use plain `return;`; `ggml_cuda_should_fuse_mul_mat` returns `false`; `block_reduce_policy` SUM/MAX return `val` for unsupported types; `ggml_backend_cuda_graph_compute` returns `GGML_STATUS_SUCCESS`; `ggml_cuda_mul_mat_id` signature changed to `enum ggml_status` with all paths returning success. |
| FA/Blackwell instance exclusions + `fa-stub.cu` | **DONE** — matched STABLE's exclusion strategy; copied `fa-stub.cu` from STABLE for SM 5.3 stubs. |
| Build 9 | **SUCCESS (EXIT=0)** — clean build, binary at `build/bin/ggml-rpc-server`. |
| Single-node shard test (node0) | **✅ SUCCESS** — 6.2 tok/s, worker computed shard on Tegra X1 (sm_53). |
| 3-node LAN test (Step B) | **✅ SUCCESS** — 6.5 tok/s across `.151`, `.152`, `.153` on port 50053. |
| **Full 11-node MTP rollout (Step A)** | **✅ COMPLETE (2026-07-20)** — all 11 nodes running MTP `ggml-rpc-server` on port 50052, dashboard wired end-to-end to MTP stack. |
| Dashboard MTP mode | **✅ OPERATIONAL** — persistent `llama-server.exe` daemon, `/health` 200, `/completion` ~6.0 tok/s with thinking trace. |

> **Key correction vs. original plan:** the plan assumed `common.cuh` + 30 CUDA files with C++17 features were the hard part. In practice the lifted `llamita.cpp` lineage (C++14-clean) plus the BF16 shim carried the port through all of them. The *only* remaining compile errors were **port-sync gaps** in backend/buffer interface initializers and a few return-type mismatches — not C++17 syntax problems. Phases A–D as written are therefore complete; do not re-run the Phase C/D `sed` scripts (they would be redundant and risk the `binbcast.cu` zeroing trap).

> **PC build tree reconciliation (2026-07-20):** the port described in Phases A–F was performed on the **node0 fleet tree** `/home/jetson/llama.cpp-mtp`. The **PC coordinator tree** `C:\llama.cpp-mtp` is a clean upstream checkout at tag `b9886` (commit `20a04b2`) with **exactly one** local modification — a 15-line RPC patch in `src/llama-model-loader.cpp` (`weight_buft_supported()`) that enables `qwen35` MTP model loading. It contains **none** of the C++17→C++14 / backend-interface / BF16-shim edits (those live only in the node0 tree). The PC tree builds the `llama-server.exe` / `llama-cli.exe` coordinators; CUDA compute runs on the node0 MTP workers (port 50052). Do not expect the PC tree to show the 231-file port diff — that diff is on node0.

---

## Background

Read this! : https://huggingface.co/coverblew/llamita.cpp?hl=en-ZA-u-fw-mon-mu-celsius

### llamita.cpp — proven reference for this exact port

`coverblew/llamita.cpp` is a **patched fork of PrismML-Eng/llama.cpp** that has *already solved* the C++17→C++14 + CUDA 10.2 port we are attempting by hand in Phases A–D. Treat it as the canonical methodology reference, not a drop-in server for Qwythos.

- **Repo:** https://github.com/coverblew/llamita.cpp — has `PATCHES.md` and `BUILD-JETSON.md` documenting the full port.
- **What it proves:** Bonsai 1-bit models (`Q1_0_g128`) compile and run on the Nano (SM 5.3 Maxwell, 4 GB, CUDA 10.2). Bonsai-8B ≈ 1.1 GB / 2.1 tok/s; Bonsai-4B ≈ 3.6 tok/s.
- **Its 7-category patch set mirrors our phases:** (1) C++17→C++14 (`if constexpr`, `std::is_same_v`, structured bindings, fold exprs), (2) CUDA 10.2 API stubs (`nv_bfloat16`, `cooperative_groups/reduce.h`, `CUDA_R_16BF`), (3) SM 5.3 Maxwell macros + flash-attn disabled via stubs, (4) ARM NEON GCC-8 broken-intrinsic workarounds, (5) linker `-lstdc++fs`, (6) **critical correctness fix in `binbcast.cu`**, (7) build system `CUDA_STANDARD 14` + flash-attn template exclusion.

**⚠️ Direct warning for Phase C:** llamita.cpp's author hit a bug where a `binbcast.cu` fold expression was replaced with `(void)0`, which *compiled cleanly but silently computed nothing* — every binary op produced garbage (model loaded, output was nonsense). Our Phase C batch `sed` script only rewrites `std::is_same_v` and greps `if constexpr`; it does **not** touch `binbcast.cu` logic. When we reach `binbcast.cu` in Phase C, the `if constexpr` → tag-dispatch conversion must preserve the actual operation bodies — do not leave a stub.

**Caveat — scope mismatch:** llamita.cpp targets **1-bit Bonsai**, not Qwythos MTP. It disables flash attention (stubbed), which is fine for 1-bit but may cost quality/speed on 8-bit. Use it for *patch technique*, not as the Qwythos server binary.

NOTE: There are C++ libaray reference documents here: "C:\Users\marti\Desktop\Cluster\C++"

**Strategic shortcut:** If the non-MTP `Qwythos-9B-v2-Q8_0.gguf` (downloading to `C:\Models`) loads on the stable fleet build (`b56f079e2`), the entire MTP CUDA port becomes deferrable — see Phase 0 below.

### Why this matters

MTP (Multi-Token Prediction) is where all new open-source models are going. Qwythos, Qwen3, and future releases use MTP draft heads. Without an MTP-capable server, the cluster is locked out of the current generation of models.

### The blocker

| Component | Version | Constraint |
|-----------|---------|------------|
| Jetson Nano | JetPack 4.6.1 | CUDA 10.2, C++14 max |
| MTP source | `20a04b2` (mid-2025) | Requires CUDA 11+, C++17 |
| NVCC 10.2 device compiler | — | C++14 only, no `if constexpr`, no `std::is_same_v` |

### What's already been done

| Patch | File | Status |
|-------|------|--------|
| Guard `cuda_bf16.h` include | `cuda.h` | ✅ Done |
| `constexpr __device__` → `const __device__` | `common.cuh` L365,374 | ✅ Done |
| `__builtin_assume` → `GGML_CUDA_ASSUME` | `fattn-vec.cuh` | ✅ Done |
| C++14 template rewrite | `convert.cuh` | ⚠️ Partial — may have `ggml_cuda_cast_impl` bug |
| Exclude `allreduce.cu` | `CMakeLists.txt` | ✅ Done |

### What remains (updated 2026-07-20)

**✅ ALL PHASES COMPLETE** — The MTP CUDA port is built, validated, and deployed across the full 11-node cluster. Dashboard at http://localhost:9090 serves the MTP model end-to-end.

No remaining work on the MTP CUDA enablement track.

---

## Work Plan

### Phase 0 — Non-MTP Qwythos v2 Q8_0 (deferred — MTP port complete)

**Status:** Superseded by the completed MTP CUDA port. The non-MTP Qwythos v2 Q8_0 path is no longer needed since the MTP model runs on the MTP stack across all 11 nodes.

### Phase A: Fix `common.cuh` (critical path — blocks everything) — ✅ COMPLETE

**File:** `ggml/src/ggml-cuda/common.cuh`  
**Status:** All C++17→C++14 fixes applied. `if constexpr` chains rewritten as `if (C)` (discarded branches contain only `static_assert`). `std::is_same_v` → `std::is_same<T, U>::value`. BF16 shim wired via `vendors/cuda_bf16.h`.

---

### Phase B: Fix `convert.cuh` — ✅ COMPLETE

**File:** `ggml/src/ggml-cuda/convert.cuh`  
**Status:** C++14 SFINAE overrides applied to `ggml_cuda_cast_impl`. BF16 intrinsic shims (`__float2bfloat16`, `__bfloat162float`) added to `cuda_bf16.h`. Compiles cleanly under NVCC 10.2.

---

### Phase C: Batch-fix remaining 19 `if constexpr` files — ✅ COMPLETE

**Files:** `mmf.cuh`, `tri.cu`, `fattn-mma-f16.cuh`, `gated_delta_net.cu`, `ggml-cuda.cu`, `fattn-tile.cuh`, `mmvf.cu`, `fattn.cu`, `rope.cu`, `binbcast.cu`, `mmq.cuh`, `concat.cu`, `topk-moe.cu`, `norm.cu`, `mmvq.cu`, `fattn-vec.cuh`, `fattn-common.cuh`, `mmid.cu`, `mma.cuh`

**Status:** All `if constexpr` → `if (C)` rewrites applied (discarded branches contain only `static_assert`). `gated_delta_net.cu` 3× `if constexpr` at lines 84/145/160 converted. All 19 files compile under NVCC 10.2 / C++14.

---

### Phase D: Fix `is_same_v` in remaining 6 files — ✅ COMPLETE

**Status:** `s/std::is_same_v</std::is_same</g` + `::value` applied mechanically across all CUDA files. 0 `is_same_v` references remain.

---

### Phase E: Build and test on node0 — ✅ COMPLETE (2026-07-18)

**Build command (proven recipe):**
```bash
cd /home/jetson/llama.cpp-mtp
rm -rf build
/home/jetson/.local/bin/cmake -B build \
  -DGGML_CUDA=ON \
  -DGGML_RPC=ON \
  -DGGML_NATIVE=OFF \
  -DGGML_CPU_ARM_ARCH=armv8.1-a+nolse \
  -DCMAKE_CUDA_ARCHITECTURES=53 \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_COMPILER=/usr/local/cuda-10.2/bin/nvcc \
  -DCMAKE_CUDA_FLAGS='--compiler-bindir /usr/bin/gcc-8' \
  -DCMAKE_C_COMPILER=gcc-9 \
  -DCMAKE_CXX_COMPILER=g++-9 \
  -DCMAKE_CUDA_STANDARD=14 \
  -DGGML_CUDA_FA=OFF \
  -DGGML_CUDA_GRAPHS=OFF \
  -DGGML_RPC_RDMA=OFF \
  -DGGML_CUDA_NCCL=OFF
cd build && make -j4 ggml-rpc-server
```

**Verification — ALL PASSED:**
1. `./bin/ggml-rpc-server --help` shows `-m MEM` flag ✅
2. Launch with `-m 3600`, check `free_mem` in logs ✅
3. Load Qwythos-9B-MTP-Q8_0.gguf from PC client over RPC ✅
4. Run a short inference, verify EXIT=0 and tok/s > 0 ✅ (6.2 tok/s single-node, 6.5 tok/s 3-node)

---

### Phase F: Deploy to fleet — ✅ COMPLETE (2026-07-20)

1. SCP `ggml-rpc-server` + `libggml-*.so` libs from node0 to all 10 workers (`.151`–`.160`) via WSL host
2. Created systemd service unit `llama-rpc-mtp.service` on all 11 nodes:
   ```ini
   [Unit]
   Description=MTP llama.cpp RPC Server
   After=network-online.target
   Wants=network-online.target
   
   [Service]
   Type=simple
   User=jetson
   WorkingDirectory=/home/jetson/llama.cpp-mtp
   ExecStart=/home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server -H 0.0.0.0 -p 50052 -t 4 -m 3600
   Restart=on-failure
   RestartSec=5
   Environment=LD_LIBRARY_PATH=/home/jetson/llama.cpp-mtp/build
   
   [Install]
   WantedBy=multi-user.target
   ```
3. Enabled and started `llama-rpc-mtp.service` on all 11 nodes
4. Verified all 11 nodes listening on port 50052 with `ggml-rpc-server` (MTP build)

---

### Phase G: Run Phase 1 with MTP model — ✅ COMPLETE (2026-07-20)

**Dashboard integration:** Updated `code/cluster_telemetry.py` to use MTP stack:
- `llama-server.exe` from `C:\llama.cpp-mtp\build\bin\`
- `--rpc` pointing to all 11 nodes on 50052
- Persistent daemon mode (not spawning `llama-cli.exe` per prompt)

**Result:** Dashboard Load → `/health` 200, Chat → ~6.0 tok/s coherent generation across all 11 nodes. Model resident persists across chats.

**Success criteria:** EXIT=0, real generation, tok/s reported ✅

---

## Dependency Chain — ✅ ALL PHASES COMPLETE

```
Phase A (common.cuh) ✅
  └─→ Phase B (convert.cuh) ✅
       └─→ Phase C (19 if constexpr files) ✅
            └─→ Phase D (6 is_same_v files) ✅
                 └─→ Phase E (build & test on node0) ✅
                      └─→ Phase F (deploy to fleet) ✅
                           └─→ Phase G (Phase 1 MTP run) ✅
                      └─→ Phase H (SSD prewarm enablement) ✅ (already satisfied by live fleet's prewarm_nfs.py)
Phase H (SSD prewarm) — parallel track, no dependency on above phases
```

---



---

## Risk Register — ✅ ALL MITIGATED

| Risk | Likelihood | Mitigation | Status |
|------|-----------|------------|--------|
| `convert.cuh` previous patch is broken | Medium | Revert and redo with tag-dispatch from Phase A | ✅ Resolved — BF16 shim worked |
| `gated_delta_net.cu` needs CUDA 11 features beyond syntax | Medium | Exclude from build if necessary (MTP draft heads don't need it) | ✅ Not compiled under current flags |
| Build takes 3+ hours on Nano | High | Accept; run overnight. Only rebuild changed files after first full build | ✅ Completed |
| MTP model still crashes after CUDA enablement | Low | Root cause was CPU-only + no `-m`; both fixed by this plan | ✅ Resolved — 6+ tok/s sustained |
| Upstream MTP repo updates break patches | Low | Pin to commit `20a04b2`; don't pull until Orin hardware arrives | ✅ Pinned |

---

## Files Reference

| Path on node0 | Purpose |
|---------------|---------|
| `/home/jetson/llama.cpp-mtp/` | MTP source tree (commit `20a04b2`) |
| `/home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/common.cuh` | Critical blocker — included by all CUDA files |
| `/home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/convert.cuh` | Type conversion templates (partially patched) |
| `/home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server` | Target binary |
| `C:\llama.cpp-mtp\build\bin\llama-cli.exe` | PC client (already built, GGML_RPC=ON) |
| `C:\Models\Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf` | MTP test model (9.11 GB) |


1. common.cuh: C++14 is_any Implementation
Replace the C++17 fold expression is_any template at line 571 with the following C++14 recursive variadic template:

C++
// C++14 Compatible is_any implementation
template<typename T, typename... Ts>
struct is_any;

template<typename T, typename U, typename... Ts>
struct is_any<T, U, Ts...> : std::integral_constant<bool, std::is_same<T, U>::value || is_any<T, Ts...>::value> {};

template<typename T>
struct is_any<T> : std::false_type {};
2. common.cuh: Tag-Dispatch Architecture
Replace the if constexpr chains (lines 578–612) with the following specialized structures. Insert original operational logic into the respective op functions.

C++
// Base template definition
template<typename T> 
struct ggml_cuda_type_ops;

// float specialization
template<> 
struct ggml_cuda_type_ops<float> { 
    static __device__ __forceinline__ void op(float * dst, const float * src, int idx) {
        // [DATA ABSENT: Insert original float branch logic here]
        dst[idx] = src[idx];
    } 
};

// half specialization
template<> 
struct ggml_cuda_type_ops<half> { 
    static __device__ __forceinline__ void op(half * dst, const half * src, int idx) {
        // [DATA ABSENT: Insert original half branch logic here]
        dst[idx] = src[idx];
    } 
};

// half2 specialization
template<> 
struct ggml_cuda_type_ops<half2> { 
    static __device__ __forceinline__ void op(half2 * dst, const half2 * src, int idx) {
        // [DATA ABSENT: Insert original half2 branch logic here]
        dst[idx] = src[idx];
    } 
};

// Wrapper function to replace the original function containing 'if constexpr'
template<typename T>
__device__ __forceinline__ void ggml_cuda_execute_op(T * dst, const T * src, int idx) {
    ggml_cuda_type_ops<T>::op(dst, src, idx);
}
3. convert.cuh: Type Conversion Fallback
Apply the following C++14 SFINAE overrides to patch ggml_cuda_cast_impl and resolve template deduction errors.

C++
// C++14 SFINAE for ggml_cuda_cast_impl
template <typename T, typename U>
__device__ __forceinline__ 
typename std::enable_if<std::is_same<T, U>::value, T>::type
ggml_cuda_cast_impl(U val) {
    return val;
}

template <typename T, typename U>
__device__ __forceinline__ 
typename std::enable_if<!std::is_same<T, U>::value, T>::type
ggml_cuda_cast_impl(U val) {
    // Explicit static cast for non-matching types
    return static_cast<T>(val);
}
4. Batch Processing Script: Phases C & D
Execute the following bash script strictly within the /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/ directory to satisfy Phase D (converting std::is_same_v).

Bash
#!/bin/bash
# MTP CUDA 10.2 Phase C & D Batch Migration Script

# Phase D: Replace std::is_same_v<T, U> with std::is_same<T, U>::value
find . -type f \( -name "*.cu" -o -name "*.cuh" \) -exec sed -i 's/std::is_same_v<\([^,]*\),\([^>]*\)>/std::is_same<\1, \2>::value/g' {} +

# Phase D (Edge cases): Replace std::is_same_v<T,U> missing spaces
find . -type f \( -name "*.cu" -o -name "*.cuh" \) -exec sed -i 's/std::is_same_v<\([^>]*\)>/std::is_same<\1>::value/g' {} +

# Diagnostic for Phase C: Locate remaining 'if constexpr' for manual tag-dispatch routing
echo "Scanning for remaining Phase C if constexpr instances requiring manual tag-dispatch mapping:"
grep -rn "if constexpr" .

The provided C++14 template meta-programming implementations achieve strict syntactic compliance with NVCC 10.2, resolving the compilation blockers outlined in the work plan. However, the structural divergence from inline if constexpr introduces variable scoping risks that demand exact manual validation during the Phase E target compilation.


One flag before you drop these into the tree: in phase_a_common_cuh_patch.cuh, the ggml_cuda_type_ops<T>::op() bodies and the alignment/nb_per_cpy branches are placeholders ([PORT ME]) — the work plan didn't include the actual original branch logic from your common.cuh, only the shape of the fix. You'll need to diff against your real file and paste each original if constexpr branch body into the matching specialization before this compiles to correct (not just syntactically valid) code. The Phase B cast patch and the Phase C/D sed script are complete as-is.

Look at: "C:\Users\marti\Desktop\Cluster\MTP enablement files"