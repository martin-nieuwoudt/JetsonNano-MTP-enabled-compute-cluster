# MTP CUDA Port — Status & Continuation Doc

**Last updated:** 2026-07-20 20:00 CEST (post code-quality audit + binary cleanup)
**BUILD STATUS: ✅ FULLY OPERATIONAL — MTP model loading + chat works on all 11 nodes via dashboard at http://localhost:9090**
**Goal: ACHIEVED — Qwythos-9B-MTP-Q8_0 loads and generates across the full 11-node cluster. Dashboard wired end-to-end to MTP stack.**

## 13. Dashboard end-to-end verification — ✅ WORKING (2026-07-19)

**Architecture change:** The dashboard no longer spawns a fresh `llama-cli.exe` per prompt (2-3 minute reload). It now launches `llama-server.exe` (persistent daemon) on Load, then all subsequent chats go through fast HTTP `/completion` calls. This was the final fix after multiple blockers.

**Verification (all 11 nodes, port 50052 — MTP stack):**
- **Load:** `Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf` → `/health` 200, model resident ✅
- **Chat:** Real generation at ~6.0 tok/s with thinking trace ✅
- **Model identification:** "I am Qwythos, an artificial intelligence created by Empero AI" ✅

**Fixed blockers on 2026-07-19:**
1. **RPC protocol mismatch:** PC `llama.cpp-mtp` binaries were built from a clean `20a04b2` checkout. The node fleet runs a CUDA-patched tree (231 modified files including backend/buffer interface ports). Fixed by SCP'ing the patched source tree from node0 → PC and rebuilding (`C:\Users\marti\Desktop\Cluster\mtp_pc_src\build_mtp_pc.bat`).
2. **Missing DLL:** `libssl-3-x64.dll` and `libcrypto-3-x64.dll` not in `C:\llama.cpp-mtp\build\bin\`. Copied from Git's mingw64.
3. **Python crashes in dashboard API:** `_server_status()` referenced `RPC_PORT` (renamed to `PORT` by import); `rpc_up` field mismatch (`rpc` vs `rpc_up`); `TOTAL_RAM_GATE_GB` too high (30→28 GB).
4. **CLI windows popping up:** Added `creationflags=CREATE_NO_WINDOW` to all subprocess calls.
5. **Model auto-ejecting:** `_server_status()` required all 11 SSH probes to pass for `running: true`. Now only checks `_RESIDENT_MODEL`.
6. **Chat timeout (TypeError: Failed to fetch):** Every prompt spawned a fresh `llama-cli.exe` reloading the model (2-3 min). Fixed by switching to persistent `llama-server.exe` daemon.
7. **llama-cli hung in interactive mode:** The MTP CLI enters interactive mode after `--prompt`. Added `--single-turn` flag so it exits after generation.

**Current PC binary paths:**
| Binary | Path | Source |
|--------|------|--------|
| `llama-server.exe` (load daemon) | `C:\llama.cpp-mtp\build\bin\llama-server.exe` | Built from PC tree `C:\llama.cpp-mtp` (clean upstream `b9886` + 1 RPC loader patch) |
| `llama-cli.exe` | `C:\llama.cpp-mtp\build\bin\llama-cli.exe` | Built from PC tree `C:\llama.cpp-mtp` (clean upstream `b9886` + 1 RPC loader patch) |
| `libssl-3-x64.dll` | `C:\llama.cpp-mtp\build\bin\libssl-3-x64.dll` | Copied from Git mingw64 |
| `libcrypto-3-x64.dll` | `C:\llama.cpp-mtp\build\bin\libcrypto-3-x64.dll` | Copied from Git mingw64 |

**Dashboard state variables (in `code/cluster_telemetry.py`):**
- `_RESIDENT_MODEL` — current loaded model path
- `_RESIDENT_PROC` — Popen handle for the `llama-server.exe` daemon
- `_RESIDENT_PORT` — llama-server HTTP port (8080)
- `_RESIDENT_CTX` — context size
- `_RESIDENT_SAMPLING` — sampling dict (`temp`/`min_p`/`top_p`/`repeat_penalty`) captured at load, now persisted through chat + ensemble (was previously dropped → stale defaults)
- `_RESIDENT_LOCK` — threading.Lock guarding all resident state

**Fleet state (11/11 — MTP stack on port 50052):**
| Node | Binary | Port | Status |
|------|--------|------|--------|
| 192.168.50.150 | `ggml-rpc-server` (MTP, CUDA-patched `20a04b2`) | 50052 | UP |
| 192.168.50.151-160 | `ggml-rpc-server` (MTP, CUDA-patched `20a04b2`) | 50052 | UP (all 10) |

**Rebuild procedure (if needed):**
```powershell
# 1. SCP patched source from node0
wsl -d Ubuntu -e bash -c 'scp -o BatchMode=yes jetson@192.168.50.150:/tmp/mtp_src.tgz /mnt/c/Users/marti/Desktop/Cluster/mtp_node_src.tgz'
# 2. Extract to build dir
tar -xzf C:\Users\marti\Desktop\Cluster\mtp_node_src.tgz -C C:\Users\marti\Desktop\Cluster\mtp_pc_src\
# 3. Build
cd C:\Users\marti\Desktop\Cluster\mtp_pc_src && cmd /c build_mtp_pc.bat
# 4. Copy to runtime location
Copy-Item "C:\Users\marti\Desktop\Cluster\mtp_pc_src\build\bin\*" "C:\llama.cpp-mtp\build\bin\" -Force
```

## 0. Swarm mode — STOPPED (2026-07-17)
- **No active swarm processes remain** on the PC or on node0 (`pgrep -af swarm` → empty; `pgrep -af build_mtp` → empty). The swarm harness (`swarm_launch.ps1`) was a no-op on its last run: the brief (`briefs/cuda_cpp17_to_cpp14.md`) was **not attached** to the launch, so the two OpenRouter models returned generic "no problem specified" replies written to `swarm/_work/tencent-hy3-free.txt` and `swarm/_work/nvidia-nemotron-3-super-120b-a12b-free.txt`. No files were patched by the swarm.
- The node0 MTP build is also **stopped** (last run ended `2026-07-17 13:01 CEST`, `EXIT=2`).
- **Conclusion:** swarm mode is off. All remaining work is manual (this doc + direct node0 edits).

---

## 1. Environment facts (immutable)

| Item | Value |
|---|---|
| node0 IP / SSH | `192.168.50.150`, user `jetson` |
| JetPack / CUDA | 4.6.1 / **CUDA 10.2** (`CUDART_VERSION` 10020) |
| C++ max standard | **C++14** (no `if constexpr` at function scope, no `std::is_same_v` convenience, etc.) |
| GPU | Maxwell SM 5.3 (`-DCMAKE_CUDA_ARCHITECTURES=53`) |
| MTP source tree | `/home/jetson/llama.cpp-mtp` (git commit `20a04b2`, branch `mtp-cuda-c14-port`) |
| Stable reference tree | `/home/jetson/llama.cpp` (build `b56f079e2`, LIVE, port 50052) — authoritative for what compiles on this Nano |
| llamita reference | `c:\Users\marti\Desktop\Cluster\llamita_ref` (coverblew/llamita.cpp — proven C++17→C++14 + CUDA 10.2 port, but targets **Bonsai 1-bit** models = SCOPE MISMATCH) |
| Build log (absolute) | `/home/jetson/mtp_build.log` |
| Build launcher | `/home/jetson/launch_build.sh` (detached via `setsid`, survives SSH drop) |
| PC workspace | `c:\Users\marti\Desktop\Cluster` (WSL path `/mnt/c/Users/marti/Desktop/Cluster`) |

**SSH/SCP patterns (PowerShell terminal — `head`/`tail` NOT available, use `sed` on node0):**
```powershell
# run a script on node0
wsl -d Ubuntu -e bash -c "ssh -o BatchMode=yes jetson@192.168.50.150 'bash -s' < /mnt/c/Users/marti/Desktop/Cluster/SCRIPT.sh"
# scp a file up
wsl -d Ubuntu -e bash -c "scp -o BatchMode=yes /mnt/c/Users/marti/Desktop/Cluster/FILE jetson@192.168.50.150:/home/jetson/"
# tail the build log
wsl -d Ubuntu -e bash -c "ssh -o BatchMode=yes jetson@192.168.50.150 'tail -30 /home/jetson/mtp_build.log; pgrep -f build_mtp.sh >/dev/null && echo RUNNING || echo STOPPED'"
```

**Build recipe** (`/home/jetson/build_mtp.sh`):
```
cmake -B build -DGGML_CUDA=ON -DGGML_RPC=ON -DGGML_NATIVE=OFF \
  -DGGML_CPU_ARM_ARCH=armv8.1-a+nolse -DCMAKE_CUDA_ARCHITECTURES=53 \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_CUDA_COMPILER=/usr/local/cuda-10.2/bin/nvcc \
  -DCMAKE_CUDA_FLAGS='--compiler-bindir /usr/bin/gcc-8' \
  -DCMAKE_C_COMPILER=gcc-9 -DCMAKE_CXX_COMPILER=g++-9 \
  -DCMAKE_CUDA_STANDARD=14 -DGGML_CUDA_FA=OFF -DGGML_CUDA_GRAPHS=OFF \
  -DGGML_RPC_RDMA=OFF -DGGML_CUDA_NCCL=OFF
make -j4 ggml-rpc-server
```

---

## 2. What is DONE

- [x] **Lifted 231 shared CUDA files** from `llamita.cpp` (C++14-clean: 0 `is_same_v`, only 3 `if constexpr` left and those are inside `gated_delta_net.cu` which is NOT compiled under current flags).
- [x] **Stripped all Bonsai `Q1_0_g128` dead code** from 8 lifted files via `strip_g128.py` (brace-counting for specializations + line-deletion for cases/macros). 186 lines removed, **0 `g128` references remain**, no dangling symbols. Files touched: `common.cuh`(6), `dequantize.cuh`(22), `vecdotq.cuh`(46), `mmq.cuh`(85), `mmq.cu`(7), `convert.cu`(10), `mmvq.cu`(8), `ggml-cuda.cu`(2).
- [x] **CMake configure passes** (ggml 0.15.3, commit `20a04b2-dirty`, CUDA+RPC backends selected).
- [x] **CPU backend compiles** (target `ggml-cpu` builds fine; failure is isolated to `ggml-cuda`).
- [x] **BF16 type shim created + wired** (`vendors/cuda_bf16.h` + `vendors/cuda.h` include guard `#if CUDART_VERSION >= 11000 ... #else #include "cuda_bf16.h"`). This is the PROVEN approach the live fleet build uses on the same Nano.
- [x] **BF16 conversion intrinsics shim added** (see §3, latest fix).
- [x] **Backend interface desync fixed** — added 3 `NULL` entries to `ggml_backend_cuda_interface` (`set_tensor_2d_async`, `get_tensor_2d_async`, `graph_optimize`).
- [x] **Buffer interfaces fixed** — added `set_tensor_2d`/`get_tensor_2d` `NULL` fields to both buffer interfaces; `init_tensor` return type changed to `enum ggml_status` with `GGML_STATUS_SUCCESS` returns; `cpy_tensor` return type changed to `bool` with proper `true`/`false` returns.
- [x] **`graph_optimize` parameter signature corrected** to `(ggml_backend_t, struct ggml_cgraph *)`.
- [x] **`ggml_cuda_should_fuse_mul_mat`** — all early returns now `return false;`.
- [x] **`block_reduce_policy` (SUM/MAX)** — unsupported-type branches now `return val;`.
- [x] **`ggml_backend_cuda_graph_compute`** — returns `GGML_STATUS_SUCCESS`.
- [x] **`ggml_cuda_mul_mat_id`** — signature changed to `enum ggml_status`, all paths return `GGML_STATUS_SUCCESS`.

---

## 3. Build blocker history — RESOLVED (build 9, 2026-07-18 14:55 CEST, EXIT=0)

The earlier `ggml-cuda.cu` return-type mismatches (§4 old) were already fixed. The remaining blockers were all **CUDA 10.2 incompatibilities in flash-attention / Blackwell template instances** that the MTP fork globs unconditionally (unlike the STABLE `llamita_cuda` reference, which comments them out). All fixed by matching STABLE's exclusion strategy + copying STABLE's `fa-stub.cu`.

| Build | Blocker | Error | Fix | Status |
|-------|---------|-------|-----|--------|
| 7 | `fattn-tile` instances | `ggml_cuda_flash_attn_ext_tile_case<...>` undefined at link | Excluded only the `fattn-tile*`/`fattn-mma*` instance globs — but left `fattn-tile.cu` (which `extern`-references the instances) compiling → still undefined | FAILED |
| 8 | `fattn.*.cu` | `ggml_cuda_flash_attn_ext` / `_supported` undefined at link | Matched STABLE: `list(FILTER GGML_SOURCES_CUDA EXCLUDE REGEX "fattn.*\.cu")` (excludes main `fattn-tile.cu` + `fattn.cu` too) | FAILED (next blocker) |
| 8 | missing `fa-stub.cu` | `ggml_cuda_flash_attn_ext` / `_supported` undefined — MTP fork lacks STABLE's stub file | Copied `/home/jetson/llamita_cuda/ggml/src/ggml-cuda/fa-stub.cu` → MTP tree (provides SM 5.3 stubs; `*.cu` glob picks it up, not matched by `fattn.*` exclude) | **DONE → build 9 SUCCESS** |

**Net CMakeLists.txt changes (MTP `ggml/src/ggml-cuda/CMakeLists.txt`):**
- `list(FILTER GGML_SOURCES_CUDA EXCLUDE REGEX "fattn.*\.cu")` (after the `*.cu` glob) — mirrors STABLE line 105.
- `list(FILTER GGML_SOURCES_CUDA EXCLUDE REGEX "mmq-instance-nvfp4.cu$")` (AFTER the `mmq*.cu` glob+append) — NVFP4 is Blackwell-only, no `type_traits` in `mmq.cuh`.
- `fattn-vec*` instance block commented out (FA=OFF, matches STABLE).
- New file `fa-stub.cu` (copied from STABLE) provides `ggml_cuda_flash_attn_ext` / `_supported` stubs so the unguarded `GGML_OP_FLASH_ATTN_EXT` call site links.

**Prior session fixes still in place:** `mmq.cu` corruption fixed; `stubs/cooperative_groups/reduce.h` created (softmax.cu).

---

## 4. Progress made this session (2026-07-18 afternoon — BUILD COMPLETE)

| Fix | File(s) | Status |
|-----|---------|--------|
| Backend interface: add 3 `NULL` entries (`set_tensor_2d_async`, `get_tensor_2d_async`, `graph_optimize`) | `ggml-cuda.cu` | ✅ Applied (2026-07-17) |
| Buffer interfaces: add `set_tensor_2d`/`get_tensor_2d` `NULL` fields; fix `init_tensor`/`cpy_tensor` return types | `ggml-cuda.cu` | ✅ Applied (2026-07-17) |
| `graph_optimize` parameter signature corrected | `ggml-cuda.cu` | ✅ Applied (2026-07-17) |
| `ggml_cuda_should_fuse_mul_mat` returns `false` | `ggml-cuda.cu` | ✅ Applied (2026-07-17) |
| `block_reduce_policy` (SUM/MAX) unsupported-type branches return `val` | `common.cuh` | ✅ Applied (2026-07-17) |
| `ggml_backend_cuda_graph_compute` returns `GGML_STATUS_SUCCESS` | `ggml-cuda.cu` | ✅ Applied (2026-07-17) |
| `ggml_cuda_mul_mat_id` signature `enum ggml_status`, all paths return success | `ggml-cuda.cu` | ✅ Applied (2026-07-17) |
| 6 return-type mismatches in `ggml-cuda.cu` | `ggml-cuda.cu` | ✅ RESOLVED (build passed) |
| `fattn.*.cu` excluded from CUDA build (matches STABLE) | `CMakeLists.txt` | ✅ Applied (build 8) |
| `mmq-instance-nvfp4.cu` excluded (Blackwell NVFP4) | `CMakeLists.txt` | ✅ Applied (build 6) |
| `fattn-vec*` instance block commented (FA=OFF) | `CMakeLists.txt` | ✅ Applied (build 7) |
| `fa-stub.cu` copied from STABLE (SM 5.3 FA stubs) | `fa-stub.cu` (new) | ✅ Applied (build 9) |
| **Clean build → `ggml-rpc-server` binary** | `build/bin/ggml-rpc-server` | ✅ **BUILD 9 SUCCESS (EXIT=0)** |

---

## 5. Build & deploy — ✅ COMPLETE (2026-07-20)

The build (build 9, EXIT=0) and the full 11-node MTP rollout (Step A) are both done. The exact next-step procedure below was the pre-deployment plan and is retained for historical reference only — it has been executed end-to-end.

1. **Inspect exact current state** of the 6 error locations + `mul_mat_id`:
```powershell
wsl -d Ubuntu -e bash -c 'ssh -o BatchMode=yes jetson@192.168.50.150 "sed -n 405,420p /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/ggml-cuda.cu; sed -n 1380,1395p /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/ggml-cuda.cu; sed -n 1785,1795p /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/ggml-cuda.cu; sed -n 4020,4040p /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/ggml-cuda.cu; sed -n 4315,4330p /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/ggml-cuda.cu; sed -n 2425,2440p /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/ggml-cuda.cu"'
```

2. **Apply precise fixes** (one-liners per function) via Python script with exact string matching.

3. **Relaunch build:**
```powershell
wsl -d Ubuntu -e bash -c "ssh -o BatchMode=yes jetson@192.168.50.150 'bash /home/jetson/launch_build.sh'"
```

4. **Monitor:** expect clean build → binary at `bin/ggml-rpc-server`.

5. **On SUCCESS:** validate `./bin/ggml-rpc-server --help` shows `-m MEM`, then deploy to fleet (Step A — ✅ COMPLETE, see §12).

---

## 6. Estimated completion

| Phase | Status | Effort remaining |
|-------|--------|------------------|
| C++17→C++14 port | ✅ 100% | 0 |
| CUDA 11→10.2 shims (BF16, etc.) | ✅ 100% | 0 |
| Backend/buffer interface sync | ✅ 100% | 0 |
| Return-type mismatches in `ggml-cuda.cu` | ✅ 100% | 0 |
| FA/Blackwell instance exclusions + `fa-stub.cu` | ✅ 100% | 0 |
| Clean build & binary validation | ✅ 100% | 0 |
| **Total** | **✅ 100% — BUILD SUCCESS** | **0** |

**Next phase (MTP enablement testing):** ✅ COMPLETE — the binary was validated against the GGUF draft-head model (vocab ~248046 tokens per `model_keys.txt`) and deployed fleet-wide (Step A, §12). No further work pending.

---

## 7. Known watch-list (MTP-only files, not from llamita)

From `onlymtp_files.txt` (27 MTP-only files). These are globbed/compiled by `CMakeLists.txt` (`file(GLOB GGML_SOURCES_CUDA "*.cu")`, except `allreduce.cu` and FA-guarded `fattn-*` instances). Candidates for the NEXT blocker **after this build passes**:

| File | Risk | Status |
|---|---|---|
| `col2im-1d.cu` | was the first BF16 failure (now fixed via shim) | ✅ rebuilt in build 9 |
| `fwht.cu` | scanned: no C++17 | ✅ rebuilt in build 9 |
| `snake.cu` | scanned: no C++17 | ✅ rebuilt in build 9 |
| `mmq-instance-nvfp4.cu` | FP4 — guarded/excluded under CUDA 10.2 flags | ✅ not compiled (safe) |
| `gated_delta_net.cu` | **3 `if constexpr` at lines 84/145/160** — C++14 conversion applied | ✅ rebuilt in build 9 |
| `fattn-*` instances | guarded by `GGML_CUDA_FA_ALL_QUANTS` (FA=OFF) → NOT compiled | safe |

**Other CUDA-version guards already verified safe:** `__hmax`/`__hmax2` guarded by `>= 11070`; `__nv_cvt_e8m0_to_bf16raw` guarded by `>= 12080`. `nv_bfloat16` was the only real version blocker (now shimmed).

---

## 8. Reference docs on hand

- `c:\Users\marti\Desktop\Cluster\C++\n4140.pdf` — **C++14 standard** (11.34 MB) — the Nano's max. Authority for legal syntax.
- `c:\Users\marti\Desktop\Cluster\C++\n4659.pdf` — C++17 draft (6.11 MB) — use to confirm what is NOT allowed (e.g. `if constexpr` at statement scope, `std::is_same_v`).
- `c:\Users\marti\Desktop\Cluster\llamita_ref\PATCHES.md` — authoritative port methodology (brace-counting strip, CUDA-10.2 shims).
- `c:\Users\marti\Desktop\Cluster\MTP CUDA Enablement Work Plan.md` — original plan (kept at root, canonical copy).
- `c:\Users\marti\Desktop\Cluster\MTP enablement files\onlymtp_files.txt` — the 27 MTP-only files.
- `c:\Users\marti\Desktop\Cluster\MTP enablement files\` — all port helper scripts (`build_mtp.sh`, `launch_build.sh`, `fix_bf16.sh`, `strip_g128.py`, `swarm_deploy.sh`, …) and their logs.
- PC helper scripts (relocated 2026-07-17 into `MTP enablement files/`): `strip_g128.py`, `fix_bf16.sh`, `inspect_node0.sh`, `build_mtp.sh`, `launch_build.sh`, `swarm_deploy.sh`, plus all `fix_*`/`check_*`/`stable_*` logs and `onlymtp_files.txt`.

---

## 9. Hard constraints (do not violate)

1. **MTP fleet is now LIVE and PERSISTENT.** The MTP build replaced the stable fleet on port 50052 via systemd unit `llama-rpc-mtp.service` (created and enabled on all 11 nodes — see §12). The original stable CUDA build (`b56f079e2`) is no longer serving.
2. **Fleet deployment is DONE.** Step A (full 11-node MTP rollout) completed 2026-07-20; dashboard wired end-to-end to the MTP stack.
3. **llamita is a different lineage (Bonsai).** Its files cannot be blindly lifted — strip Bonsai-specific quants AND CUDA-11-only assumptions.
4. **Changeable logic never hardcoded** / **data-represents-devices** invariants from the platform rules still apply to any service unit we write.

---

## 10. Build error history (for pattern recognition)

| # | % | File | Error | Fix | Status |
|---|---|---|---|---|---|
| 1 | 15% | `common.cuh`(913-916) | `GGML_TYPE_Q1_0_g128` undefined (Bonsai scope mismatch) | `strip_g128.py` removed from 8 files | DONE |
| 2 | 19% | `convert.cuh`(11) → `col2im-1d.cu`(39) | `nv_bfloat16` undefined (CUDA 11 guard in `vendors/cuda.h`) | created `cuda_bf16.h` shim + patched `cuda.h` | DONE |
| 3 | 19% | `convert.cuh`(46-47) | `__float2bfloat16`/`__bfloat162float` undefined (CUDA 11 intrinsics) | added intrinsic stubs to `cuda_bf16.h` | DONE — build relaunched 2026-07-17, passed `convert.cuh` cleanly |
| 4 | ~100% of CU list | `ggml-cuda.cu`(4251-4259) | `ggml_backend_i` initializer mismatch — struct gained `set_tensor_2d_async`/`get_tensor_2d_async`/`graph_optimize` fields the CUDA initializer lacks (shift-by-2) | add the 3 missing `NULL` entries to `ggml_backend_cuda_interface` (see §3) | DONE |
| 5 | ~100% of CU list | `ggml-cuda.cu` (6 locations) | Return-type mismatches: `void` functions returning `GGML_STATUS_SUCCESS`, kernels returning status, `enum ggml_status` functions missing returns | fix each function signature/return to match declaration | DONE (build passed) |
| 6 | link | `fattn-tile.cu` + instances | `ggml_cuda_flash_attn_ext_tile_case<...>` undefined — excluded instances but left `fattn-tile.cu` referencing them | exclude ALL `fattn.*.cu` (matches STABLE) | DONE (build 8) |
| 7 | link | missing `fa-stub.cu` | `ggml_cuda_flash_attn_ext` / `_supported` undefined — MTP fork lacks STABLE's stub | copy `fa-stub.cu` from STABLE | DONE (build 9 → SUCCESS) |

---

*All phases complete. The MTP CUDA port is built, validated, and deployed across the full 11-node cluster (Step A, §12). No further work pending.*

---

## 11. MTP shard test on node0 — ✅ SUCCESS (2026-07-18, after build 9)

**Objective:** Actually send a shard of the MTP model to the freshly-built `ggml-rpc-server` worker on `.150` and confirm it computes.

**Assets confirmed present (no download needed):**
- Model: `C:\Models\Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf` (9.3 GB, Q8_0, qwen35 arch, MTP draft-head variant)
- PC coordinator: `C:\llama.cpp-mtp\build\bin\llama-cli.exe` (PC MTP build, `b1-20a04b2`)
- Worker: node0 `ggml-rpc-server` (build 9) listening on `192.168.50.150:50053` (pid 451519)

**Command run** (`code\mtp_test_150.bat`):
```
set RPC=192.168.50.150:50053
"C:\llama.cpp-mtp\build\bin\llama-cli.exe" -m "C:\Models\Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf" -p "..." -n 64 -c 1024 --rpc "%RPC%" --no-display-prompt --temp 0.7 --repeat-penalty 1.1 -ngl 0
```
(`-ngl 0` keeps all layers on PC CPU; `--rpc` offloads the shard that fits in the worker's ~2.5 GB UMA to node0 CUDA.)

**Result — real generation, worker did the compute:**
- Coordinator output: `[ Prompt: 26.8 t/s | Generation: 6.2 t/s ]`, produced a coherent answer to the prompt.
- node0 worker log (`/home/jetson/mtp_rpc.log`): repeated `Accepted client connection` / `Client connection closed` cycles with `ggml_backend_cuda_get_available_uma_memory: final available_memory_kb: ~2531952` — i.e. the coordinator connected, allocated UMA, sent the offloaded shard, and the worker computed it on the Tegra X1 (sm_53).
- Worker still listening on 50053 after the run (no crash).

**Conclusion:** The MTP CUDA port is functionally validated end-to-end on a single node. The worker received and processed a shard of the MTP model. (Full 11-node fleet offload is a separate step — only `.150` was used here, per the single-node test scope.)

**Note on model size vs worker RAM:** `.150` has ~2.5 GB UMA, so it cannot hold the full 9.3 GB model — the coordinator offloads only the layers that fit and runs the rest on PC CPU. This is expected and still proves the shard path works. A tiny MTP model was NOT needed (and not downloaded) since the local MTP GGUF already exists.

---

## 12. MTP multi-node shard test (Step B) — ✅ SUCCESS (2026-07-19)

**Objective:** Validate the MTP coordinator↔MTP-worker RPC protocol across the LAN (not just node0 loopback) before a full 11-node rollout.

**Root cause of the original dashboard "Load" failure (2026-07-19):**
- The dashboard is wired to the **stable** stack: `C:\llama.cpp\build\bin\llama-server.exe` + stable `rpc-server` workers on port **50052** (all 11 nodes up).
- The Qwythos MTP model has architecture `qwen35`, which the **stable** server does NOT recognise → `error loading model architecture: unknown model architecture: 'qwen35'`.
- The **MTP** coordinator (`C:\llama.cpp-mtp\build\bin\llama-server.exe`) knows `qwen35`, but its RPC protocol is incompatible with the **stable** 50052 workers → `ggml-rpc.cpp:337: Remote RPC server crashed or returned malformed response`.
- **Conclusion:** the MTP model requires the MTP stack END-TO-END — both the MTP coordinator AND MTP `ggml-rpc-server` workers. The stable fleet (50052) cannot serve it.

**Step B execution (3-node proof):**
1. Tarred the proven node0 MTP worker + `libggml-*.so` libs (`/tmp/mtp_worker.tgz`, 32 MB) on `.150`.
2. Pulled tar to WSL host, then pushed to `.151`, `.152`, `.153` (node0→node scp fails: node0's key isn't trusted by peers). Extracted + recreated symlinks + launched `ggml-rpc-server -p 50053 -t 2` on each. All 3 confirmed listening on `192.168.50.{151,152,153}:50053` (Tegra X1 sm_53, ~3.0 GB UMA each).
3. Launched the MTP `llama-server` against those 3 workers:
   `C:\llama.cpp-mtp\build\bin\llama-server.exe -m Qwythos-...MTP-Q8_0.gguf --rpc 192.168.50.151:50053,192.168.50.152:50053,192.168.50.153:50053 --tensor-split 1,1,1 --port 8086 -c 2048 --no-warmup`
4. **Result:** `/health` → `HTTP 200 {"status":"ok"}`; real `/completion` returned a coherent answer at **6.5 tok/s** (prompt 22 t/s). The 3 MTP workers genuinely computed the shards across the LAN.

**Conclusion:** The MTP coordinator↔MTP-worker RPC protocol works across the LAN. The single-node result (§11) + this 3-node result together de-risked the full rollout. **Step A (full 11-node MTP rollout + dashboard MTP mode) — ✅ COMPLETE (2026-07-20).**

**Full 11-node MTP rollout (Step A) — ✅ COMPLETE (2026-07-20):**
1. Deployed the proven MTP worker (`ggml-rpc-server` + `libggml-*.so` libs) from node0 to all 10 remaining nodes (`.151`–`.160`) via SCP from WSL host.
2. Created systemd service unit `llama-rpc-mtp.service` on all 11 nodes for boot-persistent MTP daemons on port 50052 (replacing the stable fleet):
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
3. Enabled and started `llama-rpc-mtp.service` on all 11 nodes. Verified all 11 listening on port 50052 with `ggml-rpc-server` (MTP build).
4. Updated dashboard (`code/cluster_telemetry.py`) to use MTP stack: `llama-server.exe` from `C:\llama.cpp-mtp\build\bin\` with `--rpc` pointing to all 11 nodes on 50052.
5. **Result:** Dashboard Load → `/health` 200, Chat → ~6.0 tok/s coherent generation across all 11 nodes. Model resident persists across chats.

**Caveat resolved:** The MTP workers are now persistent systemd services (not manual `nohup`), surviving reboots like the stable fleet did.

---

## 14. Dashboard backend/frontend sync audit + PC-tree cleanup — ✅ DONE (2026-07-20)

**Scope:** reconcile the dashboard (`code/cluster_telemetry.py` + `code/cluster_server.py`) with the actual served state, and clean the PC build tree (`C:\llama.cpp-mtp`).

### 14.1 PC build tree (`C:\llama.cpp-mtp`) — code-quality finding
- Clean upstream checkout at **tag `b9886`** (commit `20a04b2`, dated 2026-07-06).
- **Exactly ONE local modification:** `src/llama-model-loader.cpp` — a 15-line patch in `weight_buft_supported()` enabling `qwen35` MTP model loading over RPC.
- The extensive C++17→C++14 CUDA port (Phases A–F) lives on the **node0 fleet tree** `/home/jetson/llama.cpp-mtp`, NOT the PC tree. The PC tree only builds the coordinator binaries (`llama-server.exe` / `llama-cli.exe`); CUDA compute runs on the node0 MTP workers (port 50052). Reconciled with `MTP CUDA Enablement Work Plan.md` §"PC build tree reconciliation".
- **Stale binary cleanup:** removed `llama-cli.exe.bak`, `llama-cli.exe.gs_stack`, `llama-cli.exe.norpc_bad` from `build\bin\` (dead experiment variants, unreferenced in `code/`). Live `llama-cli.exe` (19 Jul 2026) + `llama-server.exe` + `ggml-rpc-server.exe` retained.

### 14.2 Dashboard sync fixes (`code/cluster_telemetry.py` + `code/cluster_server.py`)
- **Sampling now persists end-to-end.** `_post_server_load` now stores `_RESIDENT_SAMPLING = sampling`; `_chat_completion` uses it instead of stale defaults. Deterministic profile `temp 0.1 / min_p 0.05 / top_p 0.9 / repeat_penalty 1.1` (from `code/mcp/cluster_settings.json`) is enforced unchanged.
- **Ensemble path fixed.** `_ensemble_complete` uses `_RESIDENT_SAMPLING` (was hardcoded `"temperature": 0.7`); `_post_ensemble_launch` passes `--ctx-size`/`--temp`/`--min-p`/`--top-p`/`--repeat-penalty` from UI ctx + sampling (was hardcoded `--ctx-size 2048`). `cmd_ensemble_start` added to `cluster_server.py` (was referenced by argparse but undefined → ensemble mode crashed with NameError).
- **Duplicate `btnLoad` handler removed.** Two `addEventListener` bindings (old single-only + unified) caused double-fire in ensemble mode. Only the unified handler (single + ensemble) remains.
- **UI layout:** model-status notification moved below Load/Eject/Reset buttons (no longer forces `.samp-group` to wrap); chat area broadened to fill viewport (flex-grow, removed fixed `max-height:160px` cap).
- **Validation:** `py_compile` clean on both `.py` files; `get_errors` shows only one pre-existing false-positive (unrelated eject-handler fetch); dashboard restarted, `/api/sampling` returns `{"temp":0.1,"min_p":0.05,"top_p":0.9,"repeat_penalty":1.1,"ctx_size":4096,"max_tokens":4096}`.
