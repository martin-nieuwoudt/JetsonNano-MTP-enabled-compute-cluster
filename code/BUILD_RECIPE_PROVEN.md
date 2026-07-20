# Jetson Nano llama.cpp RPC Build — Proven, Source-Traceable Recipe

**Status:** Recipe verified working (CMake configure passes, CUDA compile in progress).
**Target:** Jetson Nano (Maxwell sm_53), llama.cpp RPC distributed inference node.
**Pinned commit:** `667d72846` (tag b4501, "rpc : early register backend devices").

---

## 0. Methodology — derive requirements from SOURCE, never guess

The repeated "version translation" pain came from *guessing* which tool versions are
compatible. Every requirement below is **provable from the open-source code itself**,
not from trial and error. When repeating this build, read the source first:

| Requirement | Where to read it in the source (don't guess) |
|---|---|
| Max host GCC nvcc 10.2 accepts | `/usr/local/cuda/targets/aarch64-linux/include/crt/host_config.h` → line 138: `#error -- unsupported GNU version! gcc versions later than 8 are not supported!` |
| CUDA toolkit version | `/usr/local/cuda/version.txt` (says `CUDA Version 10.2.300`) |
| CMake flag prefix `GGML_` vs `LLAMA_` | Grep the pinned commit's `CMakeLists.txt` / `ggml/CMakeLists.txt`. At `667d72846` the options are `GGML_CUDA` / `GGML_RPC` (older `LLAMA_*` names were renamed — using them silently disables CUDA). |
| Required C++ standard | First CUDA compile error, or the project's `CMAKE_CUDA_STANDARD` requirement in `ggml/CMakeLists.txt`. CUDA 10.2's default is too low → force `14`. |
| sm_53 (Maxwell) | `nvcc --help` / `deviceQuery`, or Jetson Nano datasheet (Maxwell GM20B = compute 5.3). |

**Rule:** if a build fails on a version question, open the relevant header/CMakeLists at
the pinned commit and read the constraint. That is the ground truth.

---

## 1. Authoritative Version Manifest (verified on the booted template SD)

| Component | Version | Source of truth |
|---|---|---|
| OS | Ubuntu 20.04.6 LTS (Focal) | `/etc/os-release` |
| Kernel | 4.9.253-tegra | `uname -a` |
| GCC (host compiler) | 10.5.0 | `gcc --version` |
| GCC-8 (CUDA host compiler) | 8.4.0 | `gcc-8 --version` |
| NVCC | 10.2.300 (cuda_10.2_r440) | `nvcc --version` + `version.txt` |
| CUDA | 10.2.300 | `/usr/local/cuda/version.txt` |
| CMake | 4.3.4 | `cmake --version` (apt ships 3.16 → too old, install via pip) |
| Make | 4.2.1 | `make --version` |
| Python | 3.8.10 | `python3 --version` |
| llama.cpp commit | `667d72846` (b4501) | `git log -1 --oneline` |

**Why two GCCs:** generic `gcc`/`g++` → gcc-10 (host code, modern C++). CUDA's `nvcc`
host compiler → gcc-8 (forced, because `host_config.h` rejects > 8). These are NOT
interchangeable.

---

## 2. The exact working build recipe

```bash
# --- Toolchain env (CRITICAL: all four, non-interactive SSH has no .bashrc) ---
export CUDA_HOME=/usr/local/cuda
export CUDACXX=/usr/local/cuda/bin/nvcc
export CUDAHOSTCXX=/usr/bin/gcc-8      # <-- THE FIX: nvcc identification step
export PATH="/usr/local/cuda/bin:$PATH"

cd ~/llama.cpp
git stash && git checkout 667d72846

# --- 5 NVCC 10.2 compatibility patches (see section 4) ---
# ... (apply before cmake) ...

rm -rf build && mkdir build && cd build

CC=/usr/bin/gcc-10 CXX=/usr/bin/g++-10 cmake .. \
  -DBUILD_SHARED_LIBS=OFF \
  -DGGML_CUDA=ON \
  -DGGML_RPC=ON \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_ARCHITECTURES=53 \
  -DCMAKE_CUDA_HOST_COMPILER=/usr/bin/gcc-8 \
  -DCMAKE_CUDA_STANDARD=14 \
  -DCMAKE_C_FLAGS="-march=armv8-a -mno-outline-atomics" \
  -DCMAKE_CXX_FLAGS="-march=armv8-a -mno-outline-atomics" \
  -DGGML_CUDA_FORCE_CUB=ON

cmake --build . --parallel $(nproc)
```

Expected binaries: `build/bin/rpc-server` (port 50052), `build/bin/server`.

> NOTE: At commit `667d72846` the RPC binary is named `rpc-server` (no `llama-`
> prefix). Older docs/scripts reference `llama-rpc-server` — that name does NOT
> exist at this commit. The systemd unit is still labelled `llama-rpc.service`
> for continuity, but its `ExecStart` points at `rpc-server`.

---

## 3. The ONE gotcha that broke every prior attempt

**Symptom:** `CMake Error ... No CMAKE_CUDA_COMPILER could be found` even though
`nvcc` exists and `CUDACXX`/`PATH` are exported.

**Root cause:** During CMake's CUDA *identification* step, `nvcc` is launched WITHOUT
the `-ccbin` flag. It therefore resolves the default `gcc` on PATH (gcc-10) and dies on
`host_config.h:138`. `CUDACXX` tells CMake *where* nvcc is; it does NOT tell nvcc *which
host compiler to use*. That is `CUDAHOSTCXX`'s job.

**Fix:** `export CUDAHOSTCXX=/usr/bin/gcc-8` (proven: configure then reports
`CUDA compiler identification is NVIDIA 10.2.300 with host compiler GNU 8.4.0`).

This is the single line that converts a failing build into a passing one. It is now in
`phase5_compilation.sh`.

---

## 4. The 5 patches — each tied to a real CUDA 10.2 limitation

| # | Patch | Why (source-derived) |
|---|---|---|
| 1 | Stub `ggml/src/ggml-cuda/vendors/cuda_bf16.h` (bf16 struct) | CUDA 10.2 has no `cuda_bf16.h`; code references `nv_bfloat16`. |
| 2 | `#include <cuda_bf16.h>` → `#include "cuda_bf16.h"` in `vendors/cuda.h` | Make nvcc find the local stub, not a system header. |
| 3 | `constexpr __device__` → `__device__ const` in `common.cuh` | NVCC 10.2 rejects `constexpr` on `__device__` functions. |
| 4 | Prepend `#ifndef __builtin_assume / #define __builtin_assume(x) ((void)0)` to `fattn-common.cuh` | NVCC 10.2 lacks `__builtin_assume`. |
| 5 | `queue.push(msg)` → `queue.push(std::move(msg))` in `ggml-rpc.cpp` (×2) | GCC 10 strictness: can't copy a `unique_ptr` into the queue. |

---

## 5. Disk space — install phase fills the SD fast

**Observed:** during Phase 4 (apt + CUDA deps) the root fs reached **88% (3.1 GB free)**
on a 26 GB partition. The build itself adds several GB of `.o` files.

**Rules:**
- Monitor with `df -h /` before AND during install. If free space drops below ~2 GB,
  the NVCC build fails with spurious "No such file or directory" depfile errors that
  look like code bugs but are actually disk-full write failures.
- Prefer building in a larger volume (`/mnt/ssd`) if the SD is tight: configure the
  build dir on the SSD, not in `~/llama.cpp/build`.
- **Image compression warning:** when shrinking/cloning the golden SD image, do NOT
  `rm` system files to free space. Deleting the wrong file (e.g. under `/lib`,
  `/usr/lib`, or CUDA toolkit paths) silently breaks the next boot. Use proper image
  tooling (e.g. `zerofree` + `dd`/`pigz`, or the cloning phase) to compress the *image*,
  not the live filesystem. Preserve every system file.

---

## 6. Image compression — NEVER delete files (this broke a prior image)

**What went wrong before:** to "make space," files were deleted from the live
filesystem. That removed key system dependencies (CUDA toolkit paths, `/lib`,
`/usr/lib` entries) and the image struggled to boot afterwards. Deleting files from
a golden image is **never** the way to shrink it.

**The safe method (see `compress_image_safe.sh`):** shrink the *image*, not the
filesystem.
1. `zerofree` — writes zeros into unused blocks. File contents and metadata are
   untouched; only empty space becomes zero.
2. `dd` — image the card bit-for-bit.
3. `pigz -9` — compresses the zeros to near-nothing.

The flashed result is **bit-for-bit identical** to the original. Boot-safe by
construction. The script refuses to run unless root, the SD is a real block device,
and no partition is mounted read-write.

**Rule:** if an image is too big, compress it with `zerofree`+`pigz`. If the live
filesystem is too full to build, build on a larger volume (`/mnt/ssd`) or use a
bigger SD — do NOT `rm` system files.

---

## 7. Repeatability checklist

- [ ] `gcc-10`, `g++-10`, `gcc-8`, `g++-8` installed; generic `gcc`→gcc-10.
- [ ] CMake ≥ 3.18 (use 4.3.4 via pip; apt 3.16 is too old).
- [ ] `CUDAHOSTCXX=/usr/bin/gcc-8` exported (section 3).
- [ ] Commit `667d72846` checked out.
- [ ] All 5 patches applied (section 4) BEFORE cmake.
- [ ] `GGML_` (not `LLAMA_`) flags used.
- [ ] `df -h /` shows > 2 GB free before `cmake --build`.
- [ ] Binary `llama-rpc-server` present and `--help` runs.
