# Jetson Nano llama.cpp RPC Build — PROVEN WORKING (b56f079e2)

> **Status:** ✅ VERIFIED END-TO-END. This is the build that actually passed a live
> RPC smoke test on 2026-07-10: PC `llama-cli.exe` (CPU-only RPC client) connected
> to node0's `rpc-server` (CUDA 10.2 backend) and generated coherent text. With the
> server killed, the client fails with `Failed to connect to 192.168.50.150:50052`
> — proving the compute is genuinely offloaded to the Jetson's Maxwell GPU.
>
> **This document supersedes `code/BUILD_RECIPE_PROVEN.md`** (which described the
> earlier, *incomplete* `667d72846` attempt: gcc-10 host, 5 patches, binary name
> `llama-rpc-server`). That attempt never completed a successful link. The recipe
> below is what actually works.

---

## 0. Why this specific commit

| Fact | Detail |
|---|---|
| **Pinned commit** | `b56f079e2` (tag `b4418`, "Vulkan: Add device-specific blacklist for coopmat for the AMD proprietary driver (#11074)") |
| **Date** | 2025-01-04 |
| **Why this commit** | It is the **last commit before `46e3556e0`** ("CUDA: add BF16 support"), which introduced `cuda_bf16.h` (requires CUDA 11.0+). JetPack 4.6.1 is permanently locked to CUDA 10.2, so any newer commit fails to compile on the Nano. |
| **RPC wire protocol** | The RPC client (PC) and server (Nano) **MUST** be built from the **exact same commit**. The wire protocol changes between commits. This is why the PC is built from `b56f079e2` too — NOT a newer commit. |
| **Binary name at this commit** | `rpc-server` (in `examples/rpc/`, output at `build/bin/rpc-server`). **NOT** `llama-rpc-server`. The `llama-rpc-server` name only exists in much newer commits (post ~mid-2025 reorg into `tools/rpc/`). |
| **`--mlock` flag** | **Does NOT exist** at this commit. `rpc-server --help` shows only `-H/-p/-m`. Do not pass `--mlock`; it aborts with `error: unknown argument: --mlock`. Memory locking (if desired) must be done via the `mlockall_wrapper` setuid helper instead. |

---

## 1. Authoritative Version Manifest (verified on node0, 2026-07-10)

| Component | Version | Source of truth |
|---|---|---|
| OS | Ubuntu 18.04 (JetPack 4.6.1) | `cat /etc/os-release` |
| Kernel | 4.9.x-tegra | `uname -a` |
| **Host GCC (C/C++ for ggml-cpu, common, rpc-server)** | **gcc-9 / g++-9 (9.4.0)** | `gcc-9 --version` |
| **NVCC host compiler (forced via --compiler-bindir)** | **gcc-8 / g++-8 (8.4.0)** | `gcc-8 --version` |
| NVCC | 10.2.300 | `nvcc --version` |
| CUDA | 10.2.300 | `/usr/local/cuda-10.2/version.txt` |
| CMake | 3.27.9 (pip cmake 4.x too new; apt 3.16 too old) | `cmake --version` |
| llama.cpp commit | `b56f079e2` | `git log -1 --oneline` |

### The critical compiler split (this is the key discovery)

- **nvcc 10.2 REQUIRES gcc-8** as its host compiler. `host_config.h` rejects gcc > 8.
  → nvcc is pinned to gcc-8 via `--compiler-bindir /usr/bin/gcc-8`.
- **BUT** the host C/C++ compiler (used to compile `ggml-cpu`, `common`, `rpc-server.cpp`)
  **MUST be gcc-9**, because gcc-8's `arm_neon.h` is **missing** the `vld1q_u8_x4` and
  `vld1q_s8_x4` NEON load intrinsics. These are used by `ggml-cpu-quants.c` /
  `ggml-cpu-impl.h` and cause `implicit declaration` errors under gcc-8. gcc-9 (and 10)
  provide them.

> **This split is the single most important finding of the whole build.** Using gcc-8
> for everything (the naive approach) fails at the `ggml-cpu` stage. Using gcc-9 for
> nvcc fails at nvcc's host-config check. The working combination is:
> **nvcc → gcc-8 (bindir), host C/CXX → gcc-9.**

---

## 2. The 4 source patches (CUDA 10.2 incompatibilities)

These persist in the working tree (they survive `rm -rf build` because only the build
dir is removed). Apply them to the checked-out `b56f079e2` source BEFORE configuring.

| # | File | Change | Why |
|---|---|---|---|
| 1 | `ggml/src/ggml-cuda/common.cuh` | `static constexpr __device__ int8_t kvalues_iq4nl` → `static const __device__ int8_t kvalues_iq4nl` | NVCC 10.2 rejects `constexpr` on `__device__` variables. |
| 2 | `ggml/src/ggml-cuda/fattn-common.cuh` | `__builtin_assume(tid < D)` → `GGML_CUDA_ASSUME(tid < D)` | NVCC 10.2 lacks `__builtin_assume`. `GGML_CUDA_ASSUME` is the project's portable macro. |
| 3 | `ggml/src/ggml-cuda/fattn-vec-f16.cuh` | same `__builtin_assume` → `GGML_CUDA_ASSUME` fix | same reason |
| 4 | `ggml/src/ggml-cuda/fattn-vec-f32.cuh` | same `__builtin_assume` → `GGML_CUDA_ASSUME` fix | same reason |

> NOTE: This is **4 patches**, not the 5 described in the older `667d72846` recipe.
> The `667d72846` recipe needed a `cuda_bf16.h` stub + `queue.push(std::move(msg))`
> fix; at `b56f079e2` those code paths are either absent or already correct, so they
> are not needed. Do NOT apply the `667d72846`-era bf16 stub here.

---

## 3. The exact working configure + build

```bash
# On node0 (Jetson Nano, user jetson, IP 192.168.50.150)
cd ~/llama.cpp
git checkout b56f079e2
# ... apply the 4 patches from section 2 ...

# Configure. Host compiler = gcc-9; nvcc pinned to gcc-8 via --compiler-bindir.
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
  -DCMAKE_CUDA_STANDARD=14

# Build. The top-level Makefile does NOT expose 'rpc-server' as a target, so build
# the 'all' target (it compiles everything, then links rpc-server last).
cd build && make -j4
```

### Two non-obvious configure gotchas (both cost hours)

1. **`GGML_NATIVE=OFF` on the command line does NOT override a cached `ON`.**
   If a prior configure left `GGML_NATIVE:BOOL=ON` in `CMakeCache.txt`, re-running
   cmake with `-DGGML_NATIVE=OFF` silently keeps `ON`, and the build then tries to
   auto-detect `-mcpu=cortex-a57+crypto+nodotprod+noi8mm+nosve` — which gcc-8 can't
   parse. **Fix:** edit the cache directly:
   ```bash
   sed -i 's/^GGML_NATIVE:BOOL=ON/GGML_NATIVE:BOOL=OFF/; s/^GGML_CPU_ARM_ARCH:STRING=/GGML_CPU_ARM_ARCH:STRING=armv8.1-a+nolse/' build/CMakeCache.txt
   ```
   Then re-run the cmake configure above. Confirm the line:
   `-- Adding CPU backend variant ggml-cpu: -march=armv8.1-a+nolse`

2. **`armv8.1-a+nolse` is required, not `armv8-a`.** The `vld1q_u8_x4` intrinsic
   needs the Armv8.1-a instruction set (enabled by `-march=armv8.1-a`). `+nolse`
   disables the Large System Extensions that the Cortex-A57 doesn't have. Using
   plain `-march=armv8-a` leaves the intrinsic undeclared even under gcc-9.

### Linking note

The `rpc-server` link command (in `examples/rpc/CMakeFiles/rpc-server.dir/link.txt`)
uses the **cached** `CMAKE_CXX_COMPILER` (g++-8) — this is fine for linking objects
already compiled with gcc-9; it just invokes the linker. If you prefer to link by hand
after a partial build, run from `build/examples/rpc`:
```bash
/usr/bin/g++-8 -O3 -DNDEBUG CMakeFiles/rpc-server.dir/rpc-server.cpp.o \
  -o ../../bin/rpc-server \
  -Wl,-rpath,/home/jetson/llama.cpp/build/src:/home/jetson/llama.cpp/build/ggml/src:/home/jetson/llama.cpp/build/ggml/src/ggml-cuda:/home/jetson/llama.cpp/build/ggml/src/ggml-rpc \
  ../../src/libllama.so ../../ggml/src/libggml.so ../../ggml/src/libggml-cpu.so \
  ../../ggml/src/ggml-cuda/libggml-cuda.so ../../ggml/src/ggml-rpc/libggml-rpc.so \
  ../../ggml/src/libggml-base.so
```

**Resulting binary:** `~/llama.cpp/build/bin/rpc-server` (verified present, 24088 bytes,
`file` reports `ELF 64-bit LSB shared object, ARM aarch64`, `ldd` shows all libs resolved).

---

## 4. Launch the RPC server (node0)

```bash
# Kill any stale instance (use a pattern that does NOT match the ssh command itself)
pkill -f 'rpc-serv''er' || true

# Launch detached. NOTE: no --mlock (unsupported at this commit).
setsid nohup ~/llama.cpp/build/bin/rpc-server \
  -H 0.0.0.0 -p 50052 -m 3600 \
  > /home/jetson/llama_rpc.log 2>&1 < /dev/null &

# Verify
sleep 3
pgrep -af 'rpc-serv''er'
ss -ltn | grep 50052
cat /home/jetson/llama_rpc.log
```

Expected log:
```
create_backend: using CUDA backend
ggml_cuda_init: found 1 CUDA devices:
  Device 0: NVIDIA Tegra X1, compute capability 5.3, VMM: no
Starting RPC server on 0.0.0.0:50052, backend memory: 3600 MB
```

> **`pkill` self-match warning:** never run `pkill -f rpc-server` over SSH — the SSH
> command line contains the string `rpc-server`, so pkill kills its own parent shell.
> Use a split pattern like `'rpc-serv''er'` (or `[r]pc-server`) to avoid the match.

---

## 5. PC orchestrator build (CPU-only RPC client)

Full script: `code/pc_build/build_cpu_rpc.bat`. Summary:

- Built from the **same commit `b56f079e2`** (RPC protocol parity — keeps the RTX 5060
  free for other work during batch submits, per design intent).
- `GGML_CUDA=OFF`, `GGML_RPC=ON`, MSVC 19.44 (`VsDevCmd.bat -vcvars_ver=14.44`),
  Ninja generator.
- **2 source patches** (MSVC strictness in this old commit): `common/common.h` and
  `common/log.cpp` each need `#include <chrono>` (several files use `std::chrono`
  without including it).
- Result: `C:\llama.cpp\build\bin\llama-cli.exe` (has `--rpc`, `--flash-attn`, `-cnv`).

---

## 6. Smoke test (PROVEN 2026-07-10)

```powershell
C:\llama.cpp\build\bin\llama-cli.exe `
  -m C:\Models\tiny_test\qwen0.5b-q4km.gguf `
  -p "Hello" -n 20 --rpc 192.168.50.150:50052
```

Output (truncated): `Hello\n\nI'm trying to write a Python program that will open a
file in write mode and write some` — coherent generation, ~102 tok/s eval on the Nano.

**Negative proof (server dependency):** with the node0 `rpc-server` killed, the same
command fails:
```
Failed to connect to 192.168.50.150:50052
C:\llama.cpp\ggml\src\ggml-backend.cpp:1488: GGML_ASSERT(...) failed
```
This confirms the PC client cannot fall back to local compute — the Maxwell GPU on the
Nano is doing the work.

---

## 7. Honest caveats (for the DPG record)

- **The commit is ~18 months stale** relative to current llama.cpp (post-BF16 reorg,
  new `llama-rpc-server` binary name, many perf improvements). It was chosen purely
  because it is the newest commit that compiles under CUDA 10.2 / JetPack 4.6.1.
- **The Jetson Nano is slow** (~100 tok/s eval for a 0.5B model; a 70B model would be
  distributed across many nodes but each node is memory- and bandwidth-bound on
  1 Gbps Ethernet + UMA LPDDR4).
- **The build workarounds are non-obvious** (gcc-9-host/gcc-8-nvcc split, the
  `vld1q_u8_x4` intrinsic gap, the CMakeCache `GGML_NATIVE` override, the `armv8.1-a`
  arch, the missing `--mlock` flag). All are documented above so they are reproducible.
- **`--flash-attn` is supported** by `b56f079e2` on the PC client, but on the Nano
  CUDA 10.2 backend flash attention may not be beneficial/available for sm_53; test
  before relying on it for the 70B target.
- **Security:** the RPC server prints an explicit warning that exposing it to an open
  network is insecure (experimental feature). Bind to a trusted, isolated subnet.

---

## 8. Repeatability checklist

- [ ] JetPack 4.6.1 / CUDA 10.2 on the Nano; gcc-8 AND gcc-9 installed.
- [ ] CMake 3.27.9 (not 3.16 apt, not 4.x pip).
- [ ] Commit `b56f079e2` checked out on BOTH node0 and PC.
- [ ] 4 CUDA patches applied on node0 (section 2) BEFORE configure.
- [ ] 2 `<chrono>` patches applied on PC (section 5) BEFORE configure.
- [ ] Configure with gcc-9 host + gcc-8 nvcc bindir + `armv8.1-a+nolse` + `GGML_NATIVE=OFF`.
- [ ] `make -j4` from build root (do NOT kill it — let it finish linking rpc-server).
- [ ] Binary is `rpc-server` (not `llama-rpc-server`); launch WITHOUT `--mlock`.
- [ ] PC client connects via `--rpc 192.168.50.150:50052`.
