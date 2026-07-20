# Jetson Nano 11-Node Cluster — Work Plan

## Software Dependencies

| Software Component | Architecture | URL |
|---|---|---|
| Q-engineering Ubuntu 20.04 Image | ARM64 | [GitHub](https://github.com/Qengineering/Jetson-Nano-image) |
| llama.cpp (stable, `b56f079e2`) | Cross-platform | [GitHub](https://github.com/ggml-org/llama.cpp) — retired for MTP; kept as reference build |
| llama.cpp (MTP, `b9886`/`20a04b2`) | Cross-platform | [GitHub](https://github.com/ggml-org/llama.cpp) — **live fleet build** (CUDA 10.2 / C++14 port on node0) |
| Telegraf | ARM64 | [InfluxData](https://github.com/influxdata/telegraf/releases) |
| Eclipse Mosquitto (MQTT) | Cross-platform | [mosquitto.org](https://mosquitto.org/download/) |
| ZeroMQ | Cross-platform | [GitHub](https://github.com/zeromq/libzmq) |
| Datadog IoT Agent | ARM64 | [Datadog](https://app.datadoghq.com/account/settings/agent/latest?platform=iot) |
| SocketXP IoT Agent | ARM64 | [socketxp.com](https://www.socketxp.com/download/) |
| VS Code Remote - SSH | Windows 11 | [Marketplace](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-ssh) |
| NVIDIA Nsight Systems | Windows 11 | [nvidia.com](https://developer.nvidia.com/nsight-systems) |
| NVIDIA Nsight Compute (nvprof) | ARM64 | Bundled with CUDA 10.2 |
| jetson-stats (jtop) | ARM64 | `pip3 install jetson-stats` |
| PyCUDA 2021.1 | ARM64 | `python3 -m pip install --user pycuda==2021.1` (CUDA 10.2, Python 3.8) |

> **Dependency notes:** Azure IoT Edge Runtime, NVIDIA NeMo Framework, and NVIDIA Jetson Device Skills are excluded — not required for RPC inference. SocketXP IoT Agent is included for out-of-band reverse-tunnel SSH. The telemetry stack (Datadog / Telegraf + Mosquitto/ZeroMQ) is scripted in `code/phase11_monitoring.sh` as commented install blocks. **PyCUDA 2021.1** (CUDA 10.2 / Python 3.8) supports the Tier 1/2 distributed-compute workers, and a **FastMCP orchestration server** (`code/mcp/`) exposes RPC + Tier 1 (GEMM/embedding) + Tier 2 (MoE ring) + model-registry + simulation-method tools to the IDE agents (see the dedicated section below).
> **Two llama.cpp trees:** the **PC coordinator** (`C:\llama.cpp-mtp`) and the **node0 fleet tree** (`/home/jetson/llama.cpp-mtp`) are both the MTP build (`b9886`/`20a04b2`). The PC tree is a clean upstream checkout + one RPC-loader patch (`src/llama-model-loader.cpp`, enables `qwen35` MTP loading); the C++17→C++14 / CUDA 10.2 port lives only on the node0 tree. The old `b56f079e2` stable tree (`C:\llama.cpp`) is retained as a reference but is **not** used by the live fleet.

## Execution Summary

| # | Phase | Target | Purpose | Done |
|---|-------|--------|---------|------|
| 1 | Windows Build | Master PC | Compile `llama-cli.exe` (CPU-only RPC client) | ✅ |
| 2 | Orchestration | Master PC | SSH keys + Ansible via WSL2 | ✅ |
| 3 | Base Init | Template Node | Flash OS, inject SSH key, passwordless sudo | ✅ |
| 3b | Disk Expansion | ALL Nodes | Grow root partition to fill SD card (idempotent) | ✅ |
| 4 | Dependencies | Template Node | Compilers, headers, haveged, NFS client | ✅ |
| 5 | Compilation | Template Node | Maxwell-targeted RPC binaries | ✅ |
| 6 | Optimization | Template Node | Hardware clocks, kernel/VMM overrides, firewall + SSH key-only hardening | ✅ |
| 7 | Daemonization | Template Node | ggml-rpc-server (MTP binary) with GPU groups, memory safety | ✅ |
| 8 | Sanitization | Template Node | Wipe IDs, finalize Worker Baseline image | ✅ |
| 8b | Health Gate | Template + Cloned | Deep pre-clone health scan (services, binary, SD, clocks, CMA) — ABORT clone on FAIL | ✅ |
| 9a | Clone | Nano Zero SD | Build golden image (UI kept) = Nano Zero baseline | ✅ |
| 9b | Derive | Image copy | Copy golden, strip GUI -> worker baseline | ✅ |
| 9c | Flash | SD Cards | Flash worker img x10 + Nano Zero img x1, boot fleet | ✅ (11/11 booted) |
| 9d | Verify | All Nodes | Ansible ping test | ✅ (all nodes RPC-verified; .151–.160 PASS) |
| 9e | Promote | Nano Zero | SSD, NFS server, model storage | ✅ |
| 9e.1 | Prewarm | All Nodes + Master PC | SSD weight prewarm wired into `cluster_infer.py` (page-cache sweep before RPC upload) | ✅ |
| 9e.2 | Persistence | 10 Workers | Boot-persistent NFS mount via `fstab` + `systemd.automount` (no boot hang) | ✅ |
| 10 | Execution | Master PC | RPC inference (dashboard `llama-server.exe` daemon + `llama-cli.exe` client) | ✅ (verified via Qwythos-9B MTP across 11 nodes + model_sync push) |
| 10.5 | Output Capture | Master PC | Capture + format cluster output (raw .txt / .jsonl / .md) | ✅ |
| 11 | Monitoring | Master PC | Health check + live dashboard + fault-tolerant watchdog | ✅ (dashboard live at http://localhost:9090) |
| 12 | IDE Profiling | Master PC | Configure IDE agents for bare-metal diagnostics | ✅ (SSH keys + agent profiles wired) |
| 12b | Anti-Incast Stability | All Nodes + Master PC | Kill the 11-node connect/weight-upload storm that knocked the interconnect over (2026-07-14 incident) | ✅ (shaper + staged connect + OOM guard, verified 11/11) |
| 13 | MCP Server | Master PC | FastMCP server (27 tools): RPC + Tier1 + Tier2 + model registry + power + simulation methods | ✅ |
| 14 | PyCUDA Workers | Template Node | Install PyCUDA; GEMM/embedding/ring workers deploy at runtime via SCP | ✅ (PyCUDA on node0; workers runtime) |
| 15 | Power Management | Master PC + Dashboard | Distinct "OS Shutdown" (graceful SSH halt) vs Sonoff/Alexa 5V power; watchdog stand-down flag | ✅ |
| 16 | MTP CUDA Enablement | node0 + PC | C++17→C++14 / CUDA 10.2 port of the MTP source tree; serve MTP models (Qwythos-9B) across all 11 nodes | ✅ (built, validated, deployed — see `MTP CUDA Enablement Work Plan.md`) |

## Pre-Flight Checklist

### Hardware
- [x] All 11 Jetson Nanos boot tested individually
- [x] Gigabit Ethernet switch (1 Gbps, not 100 Mbps)
- [x] All 11 cables Cat 5e+, linking at 1 Gbps
- [x] USB 3.0 SSD for Nano Zero (ext4)
- [x] 10x microSD >=32 GB (workers) + 1x >=64 GB (Nano Zero)
- [x] Power supply 5V/4A per board (220W peak)

### Network
- [x] DHCP reservation range `192.168.50.150`-`192.168.50.160`
- [x] Master PC static IP/DHCP reservation on same subnet
- [ ] MAC addresses recorded and labeled per board

### Software & Tools
- [x] Qengineering image downloaded & verified (SHA256)
- [x] Visual Studio 2022 (MSVC 19.44) for the PC `llama-cli.exe` / `llama-server.exe` CPU-only build (no PC CUDA needed — compute runs on the Nanos)
- [x] CMake >= 3.18, Git, WSL2 + Ansible
- [x] Model GGUF files at `C:\Models\` (Qwythos-9B-MTP-Q8_0 is the live model)
- [x] USB SD card reader, Win32DiskImager or `dd`
- [x] `pip install paramiko psutil requests` (dashboard deps; `paramiko` must be under the interpreter that runs the dashboard)

## Power & Cooling

> **Why this section exists:** a single Nano is forgiving, but 11 boards under sustained
> RPC load are not. Power delivery and cooling are the two constraints that cause
> *silent* failures (random node drops, throttled tok/s, SD-card corruption) that look
> like software bugs. Get these right before Phase 1.

### Power delivery
- **Budget:** 11 × 5V/4A = **220 W peak** (from the Pre-Flight checklist). Size the supply with headroom — use a **single regulated 5V supply** (an ATX/PC PSU 5V rail, or a multi-port 5V PSU) rated for ~250–300 W, not 11 separate wall chargers.
- **Voltage tolerance:** the Nano is sensitive to 5V sag. Under load, a weak supply droops below ~4.75 V and the board browns out / reboots unpredictably. The supply must hold 5.0 V ±5% at full cluster draw.
- **Connector:** power via the **barrel jack** (J25), not the micro-USB port — the micro-USB input is limited to ~2 A and cannot sustain a loaded board. Use a 5.5 mm × 2.1 mm centre-positive barrel plug.
- **Circuit:** 220 W at 120 V ≈ 2 A; at 230 V ≈ 1 A. One dedicated circuit is fine, but do not share it with a heater/fridge. Keep cabling short and equal-length to the boards to avoid per-node voltage skew.

### Cooling
- **Active cooling is mandatory for sustained inference.** Each Nano runs `nvpmodel -m 0` + `jetson_clocks` (Phase 6), which pins max clocks — so the SoC sits at its thermal ceiling under load. A heatsink **plus fan** is required; passive-only is acceptable only for idle/boot.
- **Thermal limits:** the dashboard marks a node **WARN at 80 °C** and **FAIL at 85 °C** (`THERMAL_WARN_C` / `THERMAL_FAIL_C` in `cluster_config.py`). At 85 °C the Nano hard-throttles clocks, collapsing tok/s — so cooling headroom directly sets your real-world throughput, not RAM or network.
- **Airflow:** in a stacked/rack layout, ensure front-to-back airflow across all 11 boards. A node buried with no exhaust will throttle and drag the cluster's effective speed even if its RPC stays "up".
- **Verify:** after first full-load run, check `tegrastats` (or the dashboard thermal readout) — sustained temps should sit comfortably below 80 °C. If they don't, add airflow before trusting benchmark numbers.

## Terms

| Term | Definition |
|------|------------|
| **L4T** | Linux for Tegra -- proprietary NVIDIA Jetson drivers |
| **RPC** | Remote Procedure Call -- llama.cpp weight distribution engine |
| **Star-Topology** | Direct Master PC -> all compute nodes |
| **Golden Master** | Sanitized, fully configured OS image for cloning |
| **Maxwell (SM 5.3)** | Jetson Nano GPU architecture |
| **UMA** | Unified Memory Architecture -- CPU/GPU share LPDDR4. The Jetson Nano has **NO discrete VRAM**; the SD card is storage only and cannot expand GPU memory. All "VRAM" figures in tooling are actually **unified RAM (MemAvailable)**. |
| **DUID** | DHCP Unique Identifier from machine-id |

## Assumptions

- **Live model:** `Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf` (qwen35 arch, MTP draft heads, ~9.5 GB) — served across all 11 nodes via the MTP stack. This is the model the dashboard loads by default.
- Registry also holds (see MCP section B.6): **Qwen 2.5 72B IQ3_XS (~29.5 GB)** + **Llama 3.3 70B IQ3_XS (~29.3 GB)** at `C:\Models\` (dense, RPC layer-piping — require the MTP build too, since `qwen35`/`qwen2` arch needs the patched loader); **Codestral-22B-v0.1 (Q8_0, ~23.6 GB)** — fits PC directly; **DeepSeek-Coder-V2-Lite (Q4_K_M, 16B total / 2.4B active MoE)** — Tier 2 ring target; **DeepSeek-R1-Distill-Qwen-32B (Q6_K_L, ~27.3 GB)** — pushed to node0 SSD.
- Master PC: VS2022 (MSVC 19.44), CMake >= 3.18. **No PC CUDA** — the PC is a CPU-only RPC client/coordinator; GPU compute runs on the Nanos.
- 11x Jetson Nano (Maxwell sm_53), Gigabit switch, `192.168.50.150`-`192.168.50.160`
- Nano Zero (`192.168.50.150`) = NFS server. Workers 1-10 = RPC compute only
- VS Code as primary IDE

---

## Process

### Phase 1: Master PC (Windows) Compilation — RPC COORDINATOR (CPU-only, NO CUDA)

> **Design intent:** The PC is a pure RPC *coordinator*. It does NOT run GPU math — it
> slices the model graph and ships tensor chunks to the Jetson Nano RPC servers
> which do the Maxwell GPU compute. This keeps the PC's GPU completely free for
> other work while a batch job is submitted to the cluster. The PC therefore builds
> with `GGML_CUDA=OFF`. The build produces **two** binaries: `llama-cli.exe` (the
> one-shot RPC client, used for CLI runs and the dashboard's legacy path) and
> `llama-server.exe` (a **persistent HTTP daemon** — the dashboard launches this once
> on Load and serves all chats through its `/completion` endpoint, avoiding a
> per-prompt model reload).

- **Prerequisite:** VS2022/VS2026 (18.x) with C++ workload, CMake >= 3.18 (Strawberry Perl Ninja works fine for the CPU-only build), Git
- **CRITICAL:** Build from the **SAME commit as the Nano** (`b9886`/`20a04b2` for the MTP fleet). The RPC wire protocol changes between commits, so client and server MUST match exactly or the connection fails. The live fleet uses the **MTP build** (`C:\llama.cpp-mtp`), not the old `b56f079e2` stable tree.
- Clone: `git clone https://github.com/ggml-org/llama.cpp.git C:\llama.cpp-mtp`
- Checkout: `cd C:\llama.cpp-mtp && git checkout 20a04b2`
- **One source patch required (MTP model loading):** `src/llama-model-loader.cpp` — in `weight_buft_supported()`, add the `qwen35` weight-buffer type (15-line patch) so the MTP `qwen35` architecture loads over RPC. This is the ONLY local modification on the PC tree; the C++17→C++14 / CUDA 10.2 port lives on the node0 tree (see `MTP CUDA Enablement Work Plan.md`).
- Activate x64 MSVC: `call "C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Auxiliary\Build\vcvarsall.bat" x64` (or `VsDevCmd.bat -vcvars_ver=14.44 -arch=x64`)
- **CMake (CPU-only + RPC):**
  ```
  cd C:\llama.cpp-mtp\build
  cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=OFF -DGGML_RPC=ON -DBUILD_SHARED_LIBS=ON -DCMAKE_C_COMPILER=cl -DCMAKE_CXX_COMPILER=cl C:\llama.cpp-mtp
  cmake --build . --config Release
  ```
- Result: `C:\llama.cpp-mtp\build\bin\llama-cli.exe` (one-shot RPC client) **and** `C:\llama.cpp-mtp\build\bin\llama-server.exe` (persistent daemon the dashboard uses). Both are MTP-aware (`qwen35` arch).
- **Windows TCP Tuning:** Run `code/windows_tcp_tuning.ps1` as Administrator
- Full script: `code/pc_build/build_cpu_rpc.bat` (update the path to `C:\llama.cpp-mtp` if it still references the old tree)

### Phase 2: Orchestration Prerequisites (Master PC)

- SSH Key: `ssh-keygen -t ed25519`
- Ansible via WSL2: `sudo apt install ansible`

### Phase 3: Base Image Initialization (Template Node)

- Flash Qengineering Ubuntu 20.04 to one SD card (>=32 GB)
- Default credentials: `jetson` / `jetson`
- Bind MAC -> temporary IP on router DHCP
- Copy SSH public key to `/home/jetson/.ssh/authorized_keys`
- Passwordless sudo: see `code/phase4_dependencies.sh`

### Phase 3b: Disk Expansion (ALL Nodes)

- **Principle: whatever the SD card size is, use all of it.** The flashed image carves a fixed ~31.3 GB root partition regardless of card capacity, leaving the rest unallocated.
- Grow the partition and online-resize ext4 to reclaim 100% of the card. Safe and idempotent — `growpart` is a no-op if already maximal, `resize2fs` is safe to re-run, no files deleted.
- On a 64 GB Nano Zero card this reclaims ~31 GB; on 32 GB worker cards only the small slack (~0.7 GB). Correct either way.
- **Script:** `code/phase3b_disk_expand.sh` — run on the template node after Phase 3 and on every worker after flash (before Phase 4 dependencies).
- **First-boot automation:** `code/phase3b_firstboot.service` is installed on the template node in Phase 3b and baked into both cloned images, so every node expands its disk hands-free. **It runs on EVERY boot (NOT `ConditionFirstBoot=yes`).** `ConditionFirstBoot` was removed because on cloned images systemd regenerates `/etc/machine-id` during early boot (before the unit is evaluated), so that condition is never met and the service is silently skipped — leaving the card unexpanded. The expand script is fully idempotent, so re-running each boot is harmless and guarantees the rootfs always fills whatever card it is flashed onto (see Phase 9c).

### Phase 4: Software Dependencies (Template Node)

- Update + install: build-essential, cmake, git, pkg-config, libopenblas-dev, liblapack-dev, haveged, nfs-common
- **Script:** `code/phase4_dependencies.sh`

### Phase 5: Targeted Compilation (Template Node)

> **Live build = MTP (`b9886`/`20a04b2`).** The fleet runs the MTP source tree ported to
> CUDA 10.2 / C++14. The full port recipe (Phases A–F: the `llamita.cpp` lineage lift, BF16
> shim, backend/buffer interface sync, return-type fixes, FA/Blackwell exclusions + `fa-stub.cu`)
> is documented in **`MTP CUDA Enablement Work Plan.md`** — that is the authoritative build
> record for the live fleet. The notes below cover the **stable `b56f079e2` reference build**
> (retained as a fallback; it produces the `rpc-server` binary and does NOT serve MTP models).

- **NEVER** do `mkdir build && cd build` before `cmake -B build` (creates nested `build/build/`)
- **MTP build (live):** clone `llama.cpp` at `20a04b2`, apply the C++17→C++14 / CUDA 10.2 port from `MTP CUDA Enablement Work Plan.md`, configure with `GGML_CUDA=ON -DGGML_RPC=ON` + the gcc-9-host/gcc-8-nvcc split + `armv8.1-a+nolse` + `GGML_NATIVE=OFF`, build target `ggml-rpc-server`. Binary: `build/bin/ggml-rpc-server` (NOT `rpc-server`).
- **Stable `b56f079e2` (reference fallback):** checkout commit **`b56f079e2`** (tag `b4418`, 2025-01-04 — last commit before `46e3556e0` "CUDA: add BF16 support", which introduced `cuda_bf16.h` requiring CUDA 11.0+. JetPack 4.6.1 is locked to CUDA 10.2, so any newer commit fails to compile on the Nano). Apply the **4** NVCC 10.2 compatibility patches (Appendix A.2). Binary: `build/bin/rpc-server`.
- **Compiler split (critical, both builds):** host C/CXX = **gcc-9** (provides `vld1q_u8_x4` NEON intrinsic missing from gcc-8's `arm_neon.h`); nvcc pinned to **gcc-8** via `--compiler-bindir /usr/bin/gcc-8` (nvcc 10.2 rejects gcc > 8)
- **Script:** `code/phase5_compilation.sh` — update to the MTP recipe (ggml-rpc-server target). The old `b56f079e2` recipe (4 patches, gcc-9 host + gcc-8 nvcc bindir, `armv8.1-a+nolse`, `GGML_NATIVE=OFF`) is the reference fallback.
- Verify MTP: `./build/bin/ggml-rpc-server --help`  ← **binary is `ggml-rpc-server`** (the MTP build); the stable `b56f079e2` build produces `rpc-server` (no `ggml-` prefix).
- **Do NOT pass `--mlock`** to either binary at these commits (unsupported; use `mlockall_wrapper` setuid helper if memory locking is needed)
- **TensorRT offload:** `trtexec --onnx=model.onnx --saveEngine=model.engine --fp16` for embedding/token tasks

### Phase 6: System Optimization & Networking (Template Node)

- `sudo nvpmodel -m 0` + `sudo jetson_clocks`
- **Firewall (ufw) — enable with a default-deny incoming policy.** Allow only the ports the cluster actually uses:
  ```bash
  # SSH key-only first (see hardening note below), then firewall
  sudo ufw allow 22/tcp      # SSH (key auth only)
  sudo ufw allow 50052/tcp   # llama.cpp ggml-rpc-server (MTP)
  sudo ufw allow 2049/tcp    # NFS (Nano Zero model store, Phase 9e)
  sudo ufw allow 111/tcp     # rpcbind
  sudo ufw --force enable
  ```
  - **IPv6 caveat (this kernel):** `ip6tables` lacks the `rt` match module, so the default `/etc/ufw/before6.rules` RH0-drop line (`-m rt --rt-type 0 -j DROP`) fails to load and breaks the entire v6 ruleset ("problem running ufw-init"). Strip it before enabling so IPv6 is actually firewalled:
    ```bash
    sudo sed -i '/-m rt --rt-type 0 -j DROP/d' /etc/ufw/before6.rules
    sudo ufw --force enable && sudo ufw reload
    ```
    After this, `sudo ip6tables -S` should show `-P INPUT DROP`. **This fix is baked into `code/node_prep.sh` (step [8/8]) so every clone inherits it.**
- **SSH hardening (key-only) — MANDATORY.** The default image leaves `PasswordAuthentication yes` and the `jetson` account has a password set, so any device on the LAN can brute-force SSH. Disable password auth (key-only) on every node:
  ```bash
  sudo tee /etc/ssh/sshd_config.d/99-cluster-hardening.conf >/dev/null <<'EOF'
  PasswordAuthentication no
  KbdInteractiveAuthentication no
  ChallengeResponseAuthentication no
  PermitRootLogin no
  EOF
  sudo sshd -t && sudo systemctl restart ssh
  ```
  Verify with `sudo sshd -T | grep -i '^passwordauthentication'` → must print `passwordauthentication no`. Your ed25519 key still works. **Baked into `code/node_prep.sh` (step [7/8]).**
  - Threat model: the NAT router already blocks inbound-from-internet. The real exposure is other devices on the LAN and accidental router port-forwarding. Key-only SSH + ufw default-deny closes both. Confirm the router has **no** port-forwarding for 22 or 50052.
- Kernel/VMM overrides -> `/etc/sysctl.d/99-jetson-cluster.conf`
- Bootloader -> `cma=512M coherent_pool=64M alloc_as_vram=1` in `/boot/extlinux/extlinux.conf`
- Services: `jetson-maxperf.service` + `cluster-init.service`
- **Script:** `code/phase6_optimization.sh`
- **Config files:** `code/kernel_vmm_overrides_sysctl.conf`, `code/network_sysctl_tuning.conf`, `code/jetson_maxperf.service`, `code/bootloader_memory_contiguity.txt`

### Phase 7: Daemon Configuration (Template Node)

- Create `llama-rpc-mtp.service` (systemd unit name) that launches the **`ggml-rpc-server`** binary with `Groups=video,crypto`, memory limits, auto-restart. (The old stable build used `llama-rpc.service` + `rpc-server`; the live fleet uses the MTP service + `ggml-rpc-server`.)
- **Script:** `code/phase7_daemon.sh` — `ExecStart=/home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server -H 0.0.0.0 -p 50052 -t 4 -m 3000` (node0 template; the `-m 3000` is the Nano Zero value — see per-node `-m` below). The worker copy (9b) bumps this to `-m 3600`. The hardened deploy script `code/install_rpc_service.sh` writes `llama-rpc-mtp.service` and asserts the MTP binary exists (regression-impossible).
- **Per-node `-m` (backend memory buffer) — MANDATORY and DIFFERENT per node:** The Jetson is UMA (no discrete VRAM). Without `-m`, `ggml-rpc-server` falls back to `ggml_backend_cuda_get_device_memory`, which on the Tegra X1 returns only the tiny CUDA carveout (~14 MB free per `NvMapMemFree`) — so the node reports almost no memory and gets almost no layers. **Always pass `-m`.** node0 (Nano Zero, GUI/display server kept) shares that unified RAM with the desktop, so give it a SMALLER buffer than the headless workers: node0 `-m 3000`, workers `-m 3600`. The PC client (`llama-cli.exe --rpc`) shards layers proportionally to each server's reported `-m` (default `LLAMA_SPLIT_MODE_LAYER`, split by free memory), so a smaller node0 value automatically assigns node0 fewer layers. See Appendix A.4 for the per-node table.
- **Python GC prevention:** `code/python_gc_prevention.py` (`gc.disable()`, `malloc_trim(0)`)
- **Thread pinning (Core 0):** `os.sched_setaffinity(0, {0})`
- **Zero-copy CUDA:** `code/zero_copy_cuda_allocation.cu` (`cudaHostAllocMapped`)
- **POSIX shared memory:** Use `/dev/shm` with `shm_open`/`mmap`

### Phase 8: Identity Sanitization (Template Node)

- Purge SSH host keys, machine-id, D-Bus machine-id
- `sudo truncate -s 0 /etc/machine-id` (critical for DUID regeneration)
- Vacuum logs/cache, wipe history, power down
- **Script:** `code/phase8_sanitization.sh`
- **Security hardening is applied at clone-prep time, not here.** SSH key-only + ufw firewall (with the IPv6 `rt`-line fix) are baked into `code/node_prep.sh` (steps [7/8] and [8/8]) and run on every freshly-flashed node before it joins the fleet. Do NOT add password-auth or open ports back in during sanitization.

### Phase 9: Cloning, Distribution & Nano Zero Promotion

> **Architecture (critical):** Nano Zero (`.150`) and all workers are the SAME
> build. Workers are literally Nano Zero **with the GUI/desktop removed**. So the
> flow is: build the full thing once (UI kept) → that IS Nano Zero → make a copy →
> strip the UI from the copy → clone the UI-stripped copy to workers 1-10.
> Do NOT clone the full image to workers and disable the GUI afterwards; build the
> stripped variant from a copy so the two roles never diverge.

- **9a — Build the golden image (Nano Zero, UI kept):**
  - The fully built template node (Phases 4-8) IS Nano Zero. Keep the GUI
    (graphical desktop for local HDMI monitoring; ~0.2 GB extra RAM, acceptable).
  - `dd` this SD -> `Jetson_NanoZero_Baseline.img` (use `compress_image_safe.sh`,
    never delete files to shrink).
  - **PyCUDA 2021.1 is already installed on node0** (see the MCP/PyCUDA section, B.7),
    so the golden image captures it for all 10 worker clones — the PyCUDA workers
    (`import pycuda`) will then have it present without per-node install.
- **9b — Derive the worker image (UI stripped):**
  - Make a copy: `cp Jetson_NanoZero_Baseline.img Jetson_Worker_Baseline.img`
  - On the copy, disable the GUI: `systemctl set-default multi-user.target`
    (frees ~0.2 GB unified RAM per node for model weights). Workers are headless.
  - This is the ONLY difference between Nano Zero and workers.
- **9c — Flash the fleet:**
  - Write `Jetson_Worker_Baseline.img` to the 10x worker SD cards (32 GB).
  - Write `Jetson_NanoZero_Baseline.img` to the 1x 64 GB SD for Nano Zero.
  - **Disk expansion is wired into first boot:** `phase3b_firstboot.service`
    is baked into both images during Phase 3b and carried through the clone. It runs
    on **every** boot (no `ConditionFirstBoot` — see Phase 3b note). Every node
    auto-runs `phase3b_disk_expand.sh` on each boot, growing the root partition to
    fill whatever card it is on (32 GB worker -> small slack; 64 GB Nano Zero ->
    ~31 GB reclaimed). No per-node manual step.
    If the service was not baked in, inject it into each flashed rootfs before boot
    (see `code/phase9_cloning.sh` 9c block).
  - Boot all 11; each regenerates unique SSH keys + machine-id on first boot,
    auto-expands its disk, then auto-starts the RPC daemon.
- **9d — Verify:** `ansible jetsons -i code/hosts.ini -m ping` (all 11 SUCCESS,
  no password prompt).
- **9e — Promote Nano Zero extras:** attach USB SSD -> `/mnt/ssd`, install NFS
  server, model storage symlink at `/mnt/ssd/models/current`, export via NFS,
  mount on all nodes at `/mnt/nano-ssd`.
- **Script:** `code/phase9_cloning.sh`

### Phase 10: Execution (Master PC)

> **Primary path (live):** use the **dashboard** — `code/cluster_telemetry.py web` (http://localhost:9090). Click **Load** (launches the persistent `llama-server.exe` daemon with the Qwythos-9B MTP model across all 11 nodes), then chat in the UI. The dashboard owns model load, sampling (`temp 0.1 / min_p 0.05 / top_p 0.9 / repeat_penalty 1.1` from `code/mcp/cluster_settings.json`), and the HTTP `/completion` fan-out. This is the supported way to run the cluster.
>
> **Manual CLI path (advanced):** the `llama-cli.exe` one-shot client still works for scripted runs.

- **Live model:** `Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf` (qwen35 arch, MTP draft heads) — served across all 11 nodes via the MTP stack. Other registry models (72B/70B dense, Codestral-22B, DeepSeek variants) also run on the MTP build.
- **Coordinator binaries (Phase 1):** `C:\llama.cpp-mtp\build\bin\llama-server.exe` (persistent daemon, used by the dashboard) and `C:\llama.cpp-mtp\build\bin\llama-cli.exe` (one-shot RPC client).
- **Full cluster command (one-shot `llama-cli.exe`, Qwythos-9B MTP):**
  ```
  C:\llama.cpp-mtp\build\bin\llama-cli.exe -m C:\Models\Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf --rpc 192.168.50.150:50052,192.168.50.151:50052,192.168.50.152:50052,192.168.50.153:50052,192.168.50.154:50052,192.168.50.155:50052,192.168.50.156:50052,192.168.50.157:50052,192.168.50.158:50052,192.168.50.159:50052,192.168.50.160:50052 --tensor-split 0.85,1,1,1,1,1,1,1,1,1,1 --ctx-size 4096
  ```
  > **`--tensor-split` (handles node0's lower headroom):** The 11 values map 1:1 to the `--rpc` servers in order (node0 first). Default split is proportional to each server's reported `-m`, but an explicit `--tensor-split` overrides the free-memory probe entirely. node0 (Nano Zero, GUI kept) gets `0.85` of a worker's share; the 10 headless workers get `1`. This is the cleanest way to keep node0 from OOMing while still using all 11 nodes. If you instead tune per-node `-m` (Appendix A.4), you can drop `--tensor-split` and let the proportional split do it — but keep one or the other.
  > NOTE: `phase10_execution.ps1` in `code/` uses the `llama-cli.exe --rpc` form (CPU-only coordinator, NOT a CUDA `llama-server`). The server is the Nano `ggml-rpc-server` (Phase 5/7). The canonical, agent-facing entry point is `code/cluster_infer.py`, which adds `--tensor-split 0.85,1,1,...` (node0 headroom) and the QoS guards.
- **Smoke test (single node):** `C:\llama.cpp-mtp\build\bin\llama-cli.exe -m C:\Models\Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf -p "Hello" -n 20 --rpc 192.168.50.150:50052` → coherent generation. If the `ggml-rpc-server` is not running, the client fails with `Failed to connect to 192.168.50.150:50052` (the Maxwell GPU does the compute; there is no local fallback).

### Phase 10.5: Capturing & Formatting Output

> **Purpose:** Phase 10 documents how to *send* a task to the cluster; this section
> documents how to *capture the result* in a form a human can read and use. **Key mental model:** the Nano is the **RPC server** — it does the GPU
> math and streams tokens back to the PC. The PC `llama-cli.exe` is the **client** and
> is where the generated text actually lands (its stdout). So "retrieving output" is a
> **PC-side capture + formatting** problem, NOT a Nano retrieval problem. Nothing needs
> to be pulled off the Nano; the answer is already on your screen / in your log file.
>
> **Primary capture path (live):** the dashboard (`code/cluster_telemetry.py web`) keeps a
> running chat transcript in the browser and exposes Load/Eject/Reset + single + ensemble
> chat. For scripted/auditable capture, use the `llama-cli.exe` tiers below.

#### Where the output lives
- `llama-cli.exe` prints the generated text to **stdout on the Master PC**. The Nano
  never stores it. Capture is done with `--log-file` or a shell redirect (`>`).
- Available capture/format flags on the client (verified from `--help`):
  - `--log-file FNAME` — mirror all output (prompt + generation) to a file.
  - `-f, --file FNAME` — read the **prompt** from a file (keeps your command line clean and lets you version prompts).
  - `--grammar GRAMMAR` / `--grammar-file FNAME` — constrain output to a **BNF/JSON-schema grammar** so the result is machine-parseable (e.g. emit strict JSON you can drop into a DB or feed another tool).
  - `--no-display-prompt` — suppress the echoed prompt so the file contains **only the answer**.
  - `-cnv, --conversation` — multi-turn chat mode (system prompt via `-p`, turns via stdin).
  - `-r, --reverse-prompt PROMPT` — halt generation when a sentinel appears (useful for structured stop markers).

#### Three capture tiers (pick by need)
1. **Quick / interactive** — just run Phase 10's command; read the answer in the terminal.
   Fine for one-off questions. No file is written.
2. **Logged run (recommended default)** — add `--log-file` + `--no-display-prompt` and
   redirect, so every job is reproducible and auditable:
   ```
   C:\llama.cpp-mtp\build\bin\llama-cli.exe -m C:\Models\Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf `
     --no-display-prompt --log-file C:\Outputs\run_2026-07-10_q3.jsonl `
     --rpc 192.168.50.150:50052,192.168.50.151:50052,...(all 11)... `
     --tensor-split 0.85,1,1,1,1,1,1,1,1,1,1 --ctx-size 4096 `
     -f C:\Prompts\q3_prompt.txt -n 1024 `
     > C:\Outputs\run_2026-07-10_q3.txt 2>&1
   ```
   Result: `run_2026-07-10_q3.txt` = the human-readable answer; `...jsonl` = full log.
3. **Structured / machine-usable** — add `--grammar-file C:\Grammars\answer.json.gbnf`
   to force strict JSON (see `grammars/` in the llama.cpp tree for the schema-to-grammar
   helper). The PC then post-processes the JSON into a Markdown report. This is what the
   IDE agents (Alpha/Beta/Gamma/Delta) should consume — never raw token streams.

#### Companion script
- `code/phase10_capture.ps1` — wraps tiers 2 & 3: takes a prompt file (+ optional grammar),
  runs the client, writes a timestamped raw `.txt` + `.jsonl` log, and (if grammar was
  JSON) pretty-prints a `.json` and a `.md` summary. Run it instead of hand-typing the
  command. Example:
  ```
  pwsh code\phase10_capture.ps1 -PromptFile C:\Prompts\q3_prompt.txt `
    -Model C:\Models\Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf -GrammarFile C:\Grammars\answer.json.gbnf
  ```
- **Output sink:** because Nano Zero already serves an NFS share, the PC can write
  finished `.md`/`.json` reports into that share so any node (or another PC) can read the
  result without SSH — but the generation itself stays PC-local.

> **Do NOT** try to `scp` results *off* a Nano — there is nothing to fetch. The Nano is a
> compute slave; the PC owns the conversation and the output.

### Phase 11-12: Monitoring & IDE Agent Profiling

- **Unified telemetry:** `code/cluster_telemetry.py` (requires psutil, paramiko)
  - `python cluster_telemetry.py audit`   — one-shot deploy-gate health check (exit 0/1)
  - `python cluster_telemetry.py monitor` — live terminal dashboard (Ctrl+C to quit)
  - `python cluster_telemetry.py web`     — browser dashboard at http://localhost:9090
  - Legacy `cluster_health.py` / `cluster_monitor.py` are thin wrappers to this tool.
- **Live Gen Speed (tok/s) wiring:** the dashboard's "Gen Speed" card reads `code/rpc_metrics.json`, which is published by `code/run_rpc_stress.py`. The PC runs `llama-cli.exe`, a CPU-only RPC *client* that exposes no HTTP metrics, so Gen Speed is driven by the stress runner, not scraped from a server endpoint. Run the stress runner alongside the dashboard:
  ```
  python code\run_rpc_stress.py --rpc 192.168.50.150:50052 --loop
  python code\cluster_telemetry.py web   # then open http://localhost:9090
  ```
  The runner launches `C:\llama.cpp-mtp\build\bin\llama-cli.exe --rpc ...`, parses its `tokens per second` line, and writes `rpc_metrics.json` (atomic). The dashboard shows `Idle` when no run is active. (The primary dashboard path uses the persistent `llama-server.exe` daemon, whose tok/s is reported by the dashboard's own chat loop; the stress runner is the standalone benchmark path.)
- **Memory label note (UMA accuracy):** the dashboard's per-node card shows **"RAM avail (UMA)"** and the summary shows **"Total RAM (UMA)"**. The Jetson Nano has no discrete VRAM -- CPU and GPU share 4 GB LPDDR4, so these figures are `MemAvailable` (unified RAM), not GPU VRAM. The SD card is storage only and cannot expand memory. This label is intentional; do not change it to VRAM.
- **Node status semantics (dashboard colours):** each node card's left border and badge reflect its status:
  | Status | Meaning | Border |
  |--------|---------|--------|
  | PASS | healthy — RPC up, no thermal fault | green |
  | WARN | works but has a non-fatal caveat (GUI/display active on node0, or SoC temp in the warning band) | yellow |
  | FAIL | cannot participate — RPC port 50052 down, or thermal critical | red |
  The shared USB SSD card uses the same green/red scheme (HEALTHY / ISSUE).
- **RAM is NOT a failure condition.** `get_node_snapshot()` only FAILs on RPC-down or thermal-critical. A node with less free unified RAM (e.g. node0, which keeps its GUI) is marked WARN, not FAIL — the inference allocator (`TENSOR_SPLIT_DEFAULT` + per-node `-m` in `cluster_config.py`) allocates layers by each node's free memory at launch, so a lower-headroom node simply receives a smaller layer share. Do not add a minimum-RAM FAIL gate.
- **SSD panel (shared USB SSD):** rendered as a node-sized card at the top of the grid. It is populated by `get_ssd_status()`, which SSH-probes node0 and reads the live `df -T` of the mount (`SSD_MOUNT`, default `/mnt/ssd`). Fields shown: plugged-into IP, mount, backing device, filesystem, capacity, used, free, usage %, access (rw/ro), and SMB share path. The `df -T` columns are `Filesystem Type 1B-blocks Used Available Use% Mounted-on` — parse `$3`=size, `$4`=used, `$5`=avail, `$6`=use% (do NOT recompute size as used+avail, and do NOT swap used/avail). Health = mount present + writable + not read-only.
- **Dashboard auto-start (Master PC):** create a Startup-folder shortcut so the dashboard launches on logon (a Scheduled Task is not used — UAC elevation is unreliable in headless contexts). Shortcut at `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\ClusterTelemetry.lnk`:
  - Target: `C:\Python314\pythonw.exe` (headless — no console window)
  - Arguments: `"C:\Users\marti\Desktop\Cluster\code\cluster_telemetry.py" web`
  - Start in: `C:\Users\marti\Desktop\Cluster\code`
  - Run: minimized
  The server must run under `C:\Python314\python.exe` (the `.venv` interpreter lacks `paramiko`).
- **mlockall wrapper:** `code/mlockall_wrapper.cpp`
- **Profiling tools:** `nsys profile`, `nvprof` (legacy -- Maxwell SM 5.3), `tegrastats`, `jtop` (jetson-stats)
- **VS Code optimize:** `code/vscode_remote_settings.json` -> `"remote.SSH.defaultExtensions": []`
- **VS Code workspace:** `code/cluster.code-workspace`

---

## Phase 15: Power Management (OS Shutdown vs Power)

> **Core principle — two distinct concerns, never conflated:**
> 1. **OS Shutdown** = graceful halt of the 11 boards' operating systems (stop
>    `ggml-rpc-server` (or `systemctl stop llama-rpc-mtp.service`), unmount NFS, `sync`, `shutdown -h now`). This is a **software**
>    action the dashboard button drives. The button is labelled **"OS Shutdown"**,
>    never "Power Off", so nobody mistakes a graceful halt for a hard power cut.
> 2. **Power (5V cut / restore)** = a **Sonoff switch** on the cluster's 5V rail,
>    toggled by **Amazon Alexa voice** ("Alexa, turn on/off the cluster"). There is
>    **no API** the dashboard can call — the switch is a manual/voice bridge. The
>    dashboard only *reacts* to it (polls for nodes coming up after "Alexa, on").

### Why this split
- A Jetson Nano has **no remote power management** (no IPMI/AMT/PDU). `shutdown -h now`
  halts the OS but the board still draws from the barrel jack. True zero-power needs a
  *controllable* 5V supply — which the Sonoff provides. So software owns graceful halt;
  the Sonoff owns actual power. Keeping them separate avoids a fragile reverse-engineered
  Sonoff API and a dangerous "one button does both" footgun.

### ON flow (voice + verify)
1. **You:** "Alexa, turn on cluster" → Sonoff restores 5V to all 11 boards.
2. **Dashboard "Power On" button** → calls `power_on_verify()` (MCP `cluster.power.*`):
   polls every node's RPC port 50052 until all 11 answer (or timeout), then flips
   cluster mode `maintenance` → `normal` so the watchdog re-arms.
3. **Boot-order caveat:** all boards get 5V at once, but workers mount node0's NFS.
   node0 must be ready *before* workers mount, so the worker firstboot needs an
   **NFS wait-and-retry** (not fail-fast). `code/phase3b_firstboot.service` already
   runs every boot — add the NFS-wait there (see note below).

### OFF flow (graceful, then optional voice cut)
1. **Dashboard "OS Shutdown" button** → calls `power_os_shutdown(confirm=True)`:
   - Sets cluster mode → `maintenance` **first** (shared flag in `cluster_config.py`).
   - The fault-tolerant watchdog (`cluster_watchdog.py`) reads this flag and **stands
     down** — it does NOT re-slice or re-admit nodes during the shutdown, so it never
     fights the halt or spams false fault events. Single source of truth; both sides
     import `get_cluster_mode()` / `set_cluster_mode()`.
   - **Order: workers (1–10) FIRST, node0 (NFS server) LAST** — workers unmount
     node0's NFS cleanly instead of hanging on a dead server.
   - Per node: `pkill ggml-rpc-server` (or `systemctl stop llama-rpc-mtp.service`) → `umount /mnt/nano-ssd` → `sync` → `shutdown -h now`.
   - Returns per-node result (acknowledged / timeout / unreachable) — not a binary done.
2. **You (optional):** "Alexa, turn off cluster" → Sonoff cuts 5V for true zero-power.

### Safety gates
- `power_os_shutdown` requires `confirm=True` — single-click destructive action on 11
  nodes is gated. Re-clicking after shutdown reports "unreachable" (idempotent), not error.
- The watchdog stand-down flag prevents the two systems from fighting.
- Physical power remains in your voice — software can never cut 5V on its own.

### Files touched (this phase)
| File | Change |
|------|--------|
| `code/mcp/cluster_config.py` | Added `CLUSTER_STATE_FILE`, `CLUSTER_MODE_*`, `get_cluster_mode()` / `set_cluster_mode()` (single source of truth for the flag) |
| `code/cluster_watchdog.py` | Reads `get_cluster_mode()`; stands down (no re-slice/re-admit) while `maintenance` |
| `code/mcp/cluster_mcp_server.py` | Added `cluster.power.*` namespace: `power_os_shutdown(confirm)`, `power_on_verify(timeout_s)` (tools 23–24); later `cluster.method.*` added tools 25–27 |


---

## Phase 12b: Anti-Incast Stability (2026-07-14 Outage Root-Cause Fix)

> **Why this phase exists:** on 2026-07-14 the cluster suffered a multi-mode
> outage — wrong daemon on boot after a physical move, an OOM kill on the marginal
> node (160), and a connect/disconnect storm that made the dashboard report "RPCs
> down" while the daemons stayed alive. All three were root-caused and made
> permanently impossible. The storm was the dominant symptom: the llama.cpp RPC
> client opens **all 11 node connections at once** and blasts each node's weight
> shard simultaneously. That incast burst overwhelms the small 1 Gbps interconnect
> switch → packet drops → TCP resets → nodes log `recv failed (bytes_recv=0,
> size_to_recv=1)` → reconnect loop. The fix is **two-layer** and **boot-persistent**.

### Layer A — Node-side egress shaper (always-on, before the daemon)
- `code/apply_rpc_shaper.sh` — idempotent `tc` HTB qdisc on `eth0` that caps
  RPC-port (50052) egress at **850 Mbit** with a **64 KB burst bucket**, smoothing
  the incast spike so a single node can never flood the switch.
- `code/llama-rpc-shape.service` — root `oneshot`, ordered **`Before=llama-rpc-mtp.service`**
  (and `Wants=network-online.target`), so the shaper is live **before** the daemon
  binds the port on every boot. `RemainAfterExit=yes` keeps it asserted.
- Tunables live ONLY in `code/mcp/cluster_config.py` (`RPC_SHAPER_*` block):
  `RPC_SHAPER_ENABLED`, `RPC_SHAPER_IFACE="eth0"`, `RPC_SHAPER_RATE="850mbit"`,
  `RPC_SHAPER_BURST="64kb"`, `RPC_SHAPER_PORT=RPC_PORT`.

### Layer B — Client-side staged connect + OOM guard
- `code/cluster_infer.py::build_rpc_list_staged()` — pre-warms nodes **3-at-a-time**
  (`STAGE_NODES_AT_ONCE=3`) with a **4 s settle** (`STAGE_SETTLE_S=4.0`) so the
  weight-upload burst is spread out instead of simultaneous. Returns the full
  comma-list (tensor split still needs every server named). Skipped under `--no-qos`.
- `code/cluster_infer.py::guard_model_fits_weakest_node()` — estimates per-node
  shard + 35% UMA overhead (`OOM_GUARD_OVERHEAD_FRAC=0.35`) and **aborts** (exit 4)
  if it would exceed `OOM_GUARD_WEAKEST_HEADROOM_FRAC=0.80` × node160's 3.47 GB
  `MemAvailable`. Refuses the BF16 9B model; passes Q8_0 Qwythos (~0.83 GB/node).

### Hardening (regression-impossible)
- `code/install_rpc_service.sh` — now **deletes any old `rpc-server.service`** unit
  and **asserts the MTP `ggml-rpc-server` binary exists** before enabling; deploys
  the shaper script + shape unit; restarts both. Re-running it can never regress to
  the old binary.
- `code/verify_fleet.sh` — per-node proof: `bin=MTP old=GONE shape=enabled
  qdisc=SHAPED listen=UP`. Exits non-zero on any failure.

### Verification (2026-07-14, all 11 nodes)
```
192.168.50.150: bin=MTP old=GONE shape=enabled qdisc=SHAPED listen=UP -> OK
... (all 11) ...
===== ALL GREEN =====
# PC-side: 11/11 OPEN on port 50052
```

---

## Automation Scripts

| File | Purpose |
|------|---------|
| `code/cluster_deploy.py` | Unified Python orchestrator (init, launch, terminate, poweroff, profile, dashboard) |
| `code/run_cluster.bat` | Full orchestration batch script |
| `code/cluster_deploy.yml` | Ansible playbook (full deployment) |
| `code/nvme_swap_tasks.yml` | Ansible swap-file tasks (append to playbook) |
| `code/hosts.ini` | Ansible inventory |
| `code/ssh_config.txt` | Windows SSH config for all 11 nodes |
| `code/mcp/cluster_mcp_server.py` | MCP server (27 tools) wrapping RPC + Tier1 + Tier2 + model registry + power + method |
| `code/mcp/cluster_config.py` | Single source of truth (nodes / ports / models / SSH) imported by the server |
| `code/apply_rpc_shaper.sh` | Idempotent `tc` egress shaper for the RPC port (Phase 12b, anti-incast) |
| `code/llama-rpc-shape.service` | systemd oneshot, `Before=llama-rpc-mtp.service`, applies the shaper on boot (Phase 12b) |
| `code/install_rpc_service.sh` | Hardened deploy: MTP daemon + shaper, deletes old unit, asserts MTP binary (Phase 12b) |
| `code/verify_fleet.sh` | Per-node proof that all 3 failure modes are fixed (Phase 12b) |
| `code/mcp/workers/jetson_worker.py` | Tier 1 GEMM worker (port 9999) — SCP-pushed to Jetsons at runtime |
| `code/mcp/workers/jetson_embedding_worker.py` | Tier 1 embedding worker (port 9998) — SCP-pushed at runtime |
| `code/mcp/workers/jetson_ring_worker.py` | Tier 2 MoE ring worker (port 8888) — SCP-pushed at runtime |
| `code/dl_generic_model.py` | Resumable range-segmented model downloader (used by `model_download`) |

## Supporting Config Files

| File | Destination |
|------|-------------|
| `code/kernel_vmm_overrides_sysctl.conf` | `/etc/sysctl.d/99-jetson-cluster.conf` |
| `code/network_sysctl_tuning.conf` | Append to `/etc/sysctl.conf` |
| `code/bootloader_memory_contiguity.txt` | `/boot/extlinux/extlinux.conf` APPEND line |
| `code/jetson_maxperf.service` | `/etc/systemd/system/jetson-maxperf.service` |
| `code/vscode_remote_settings.json` | VS Code User `settings.json` |
| `code/windows_tcp_tuning.ps1` | Run as Administrator on Windows 11 |
| `code/bare_metal_os_hardening.sh` | Run on worker nodes for memory extraction |
| `code/copilot_instructions.md` | GitHub Copilot context instructions |
| `code/mcp/cluster_config.py` | PC-side single source of truth (imported by MCP server + workers + watchdog) |

## Phase Scripts

| File | Phase | Run On |
|------|-------|--------|
| `code/phase4_dependencies.sh` | 4 | Template Node |
| `code/phase5_compilation.sh` | 5 | Template Node |
| `code/phase6_optimization.sh` | 6 | Template Node |
| `code/phase7_daemon.sh` | 7 | Template Node |
| `code/phase8_sanitization.sh` | 8 | Template Node |
| `code/phase9_cloning.sh` | 9 | Master PC / Nano Zero |
| `code/phase10_execution.ps1` | 10 | Master PC |
| `code/phase10_capture.ps1` | 10.5 | Master PC |
| `code/phase11_monitoring.sh` | 11 | Template Node |
| `code/apply_rpc_shaper.sh` | 12b | All Nodes (boot) |
| `code/install_rpc_service.sh` | 12b | Master PC (deploy) |
| `code/verify_fleet.sh` | 12b | Master PC (verify) |

## Deduplication Notes

All duplicates are resolved. `cluster_deploy.py` unifies init/launch/terminate/poweroff/profile/dashboard and delegates daemon launch to `cluster_qos.relaunch_rpc_daemon` (single launch implementation). `run_cluster.bat` is the canonical orchestration script.

## Model Management (PC-side, single source of truth)

All model download / verify / sync logic is unified. Changeable facts (URLs, PC paths,
node0 model dir, SSH identity) live ONLY in `code/mcp/cluster_config.py` (`MODELS` registry
+ `MODEL_DIR_ON_NODE0`, `MODEL_NODE_IP`, `SSH_USER`). No script hardcodes a model URL or path.

| File | Role | Status |
|------|------|--------|
| `code/dl_generic_model.py` | **The only** GGUF downloader (resumable, range-segmented). Writes `<out>.sha256` sidecar. | canonical |
| `code/model_sync.py` | Registry-driven wrapper: `download <key>` / `verify <key>` / `push <key>`. Forwards to `dl_generic_model.py`; SCPs GGUF+sidecar to node0. | canonical |
| `code/sync_model.ps1` | **The only** PowerShell sync tool: `-Model <key> [-Direction PCtoNode0\|Node0toPC] [-VerifyOnly]`. Resolves paths from `cluster_config`. | canonical |
| `code/resume_after_cooldown.ps1` | Cooldown-resume: relaunches `model_sync.py download <key>` detached after a corrupt download. | canonical |

**Removed (do not recreate):** `dl_node0.sh`, `dl_parallel_node0.sh`, `scp_qwen_to_node0.ps1`, `verify_qwen_node0.ps1`, `download_orchestrator.ps1`, `tegrastats_telemetry.py` (orphan; tegrastats already owned by `cluster_telemetry.py`). Also removed: the deprecated download shims `dl_llama_pc.py`, `dl_node0.py`, `fetch_qwen_all_pc.py`, `fetch_qwen_part0_pc.py` (superseded by `model_sync.py` / `sync_model.ps1`).

**Sidecar convention (canonical):** `<basename>.gguf.sha256` containing `"<hexhash>  <basename>"`
(two spaces). Written by `dl_generic_model.py` / `model_sync.py`; read by `cluster_qos.preflight_model_hash`
and `sync_model.ps1`. The old `qwen_pc.sha256` name is retired.

**Model storage architecture (Phase 9e):** ALL GGUFs live on node0's USB SSD (`/mnt/ssd/models`),
NFS-exported to workers (`/mnt/nano-ssd`). PC is the SOURCE of truth; default sync direction is
PC→node0 (push). `Node0toPC` is explicit recovery only.

---

## MCP Orchestration & PyCUDA Distributed Compute Layer

> **Scope:** This layer wraps the existing llama.cpp RPC inference (Phase 10) AND adds a
> separate PyCUDA memory-sharding distributed-compute paradigm: Tier 1 (star-topology
> GEMM + embedding) and Tier 2 (MoE expert-parallel ring). All of it is driven from the
> PC orchestrator and exposed to the IDE agents (Alpha/Beta/Gamma/Delta) as MCP tools.
> This is the canonical, authoritative description of the MCP server and the PyCUDA
> workers. The design intent came from `memory sharding and MCP.txt`; **this section is
> the single source of truth for the MCP server and PyCUDA workers.**

### B.0 Architecture

- **MCP server** (`code/mcp/cluster_mcp_server.py`) runs on the **Master PC** (Windows, Python 3.14 via `py -3.14`). It uses `FastMCP("jetson-cluster")` and `mcp.run()` (stdio transport), so VS Code Copilot / Claude Desktop can call its tools.
- **Single source of truth** (`code/mcp/cluster_config.py`): every changeable fact (node IPs, ports, shard counts, model registry, SSH identity, PC paths) lives here and ONLY here. Tool code reads `cfg.*`; it never hardcodes node lists/ports/paths. This satisfies the architectural invariant "Changeable logic is never hardcoded."
- **PyCUDA workers** (`code/mcp/workers/*.py`) run on the **Jetsons**. They are NOT baked into the golden image — they are SCP-pushed and launched at runtime by the MCP tools (`gemm_push_workers` / `gemm_start_workers`, etc.). This keeps the image lean and lets worker code iterate without re-cloning.
- **PyCUDA itself IS baked into the golden image**: it was installed on node0 (the clone template) before Phase 9a capture, so all 10 worker clones inherit it. See B.7.

### B.1 Port map (must never collide)

| Port | Owner | Purpose |
|------|-------|---------
| 50052 | llama.cpp `ggml-rpc-server` (MTP) | Dense + MTP model layer-piping (RPC) |
| 9999 | Tier 1 GEMM worker | FP16 matrix self-mul (`A @ A^T`) |
| 9998 | Tier 1 embedding worker | token-id → float16 embedding projection |
| 8888 | Tier 2 ring worker | MoE expert-parallel ring |

All four are defined in `cluster_config.py` (`RPC_PORT`, `GEMM_PORT`, `EMBED_PORT`, `RING_PORT`). RPC stays on 50052; the PyCUDA workers use the other three.

### B.2 MCP tool namespaces (27 tools)

| Namespace | Tools | Purpose |
|-----------|-------|---------
| `cluster.rpc.*` | `rpc_audit`, `rpc_deploy(mode)`, `rpc_capture(prompt_file, model_key, tokens, out_dir, grammar_file)`, `rpc_telemetry_snapshot` | Wrap existing llama.cpp RPC ops (health, deploy, capture, telemetry) |
| `cluster.fleet.*` | `fleet_nodes`, `fleet_ssh_health`, `fleet_rebalance(shard_map)`, `fleet_scaling_benchmark(rows, cols, shards)` | Node fleet state, fault tolerance, scaling benchmark |
| `cluster.gemm.*` | `gemm_push_workers`, `gemm_start_workers`, `gemm_stop_workers`, `gemm_run(rows, cols)` | Tier 1 star-topology FP16 matrix sharding |
| `cluster.embed.*` | `embed_push_workers`, `embed_start_workers`, `embed_stop_workers`, `embed_run(paragraphs, tokens_per_paragraph)` | Tier 1 token→embedding sharding |
| `cluster.ring.*` | `ring_push_workers`, `ring_start_workers`, `ring_stop_workers`, `ring_run(model_key, batches)` | Tier 2 MoE expert-parallel ring |
| `cluster.model.*` | `model_list`, `model_download(model_key, segments, stagger)` | Model registry + resumable download |
| `cluster.power.*` | `power_os_shutdown(confirm)`, `power_on_verify(timeout_s)` | OS Shutdown (graceful SSH halt, workers-first/node0-last) + power-on verify (poll + watchdog re-arm) |
| `cluster.method.*` | `method_list`, `method_run(method, node_ip="", overrides="", timeout_s=120)`, `method_push` | Anti-Dark-Forest simulation methods (marl, montecarlo, kl_div, …) — list, run locally or on a node, push |

All tools read changeable values from `cfg.*` (43 references verified). No hardcoded node IPs/ports in tool logic. The `cluster.power.*` tools additionally share the `maintenance` flag with `cluster_watchdog.py` via `cluster_config.get_cluster_mode()` / `set_cluster_mode()` — single source of truth, so the watchdog stands down during an OS shutdown and never fights it.

### B.3 Tier 1 — GEMM worker (`jetson_worker.py`, port 9999)

- **Kernel:** `matMulFP16` — FP16 storage, FP32 accumulation, no Tensor Cores (Maxwell SM 5.3). Computes `C = A @ A^T`.
- **Wire protocol (PC → worker):**
  - Send 16-byte header: `struct.pack("!III", seq_id, rows, cols) + b"\x00\x00\x00\x00"` (4 pad bytes).
  - Send `rows*cols*2` bytes float16 payload.
  - Worker replies 8-byte header `struct.pack("!II", seq_id, len)` + float16 result (`rows × rows`).
- **Throttling:** PC side uses `asyncio.Semaphore(MAX_CONCURRENT_NET_STREAMS=4)` to protect the 1-gigE switch.
- **Launch:** `python3 /home/jetson/jetson_worker.py --port 9999` (via `gemm_start_workers`, ssh -f).

### B.4 Tier 1 — Embedding worker (`jetson_embedding_worker.py`, port 9998)

- **Kernel:** `projectEmbeddings` — maps each token id to a row of a static `VOCAB_SIZE × EMBEDDING_DIM` weight matrix (`VOCAB_SIZE=50000`, `EMBEDDING_DIM=768`). Weights are `np.random.default_rng(0).standard_normal(...).astype(np.float16)` (deterministic mock).
- **Wire protocol (PC → worker):**
  - Send 12-byte header: `struct.pack("!II", seq_id, num_tokens).ljust(12, b"\x00")`.
  - Send `num_tokens*4` bytes int32 token ids.
  - Worker replies 8-byte header `struct.pack("!II", seq_id, len)` + float16 result (`num_tokens × 768`).
- **Launch:** `python3 /home/jetson/jetson_embedding_worker.py --port 9998`.

### B.5 Tier 2 — MoE ring worker (`jetson_ring_worker.py`, port 8888)

- **Topology:** logical ring. PC pumps token batches into the head (Jetson 0); each node processes the experts it owns, then forwards the remaining batch to the next node. The final (tail) node returns the completed hidden-state tensor to the PC.
- **Kernel:** `evaluate_expert_gemm` is a **RESEARCH-GRADE PLACEHOLDER** (identity pass-through). The source design doc's kernel was a stub; the real expert FFN math must be written against actual MoE weights (e.g. DeepSeek-Coder-V2-Lite safetensors) before production. This worker validates the ring **transport + double-buffering** pattern only.
- **Constants:** `HIDDEN_DIM=4096`, `BATCH_SIZE=16`, `SEQUENCE_LEN=512` (MUST match `RING_*` in `cluster_config.py`).
- **Wire protocol (PC → head):**
  - Send 8-byte header: `struct.pack("!II", batch_id, num_floats)` where `num_floats = BATCH_SIZE*SEQUENCE_LEN*HIDDEN_DIM`.
  - Send `num_floats*4` bytes FP32 payload.
  - Tail replies 8-byte header `struct.pack("!II", batch_id, len)` + FP32 tensor.
- **Tail safety:** worker forwards to `next_node_ip` ONLY if `next_node_ip != "127.0.0.1"` (default), preventing a closed-ring infinite loop.
- **Boot order:** `ring_start_workers` launches Jetson 10 → … → Jetson 0 (reversed) so downstream sockets listen before data arrives.
- **Launch:** `python3 /home/jetson/jetson_ring_worker.py --port 8888 --next-ip <next> --next-port 8888`.

### B.6 Model registry (`cluster_config.py` → `MODELS`)

| Key | Kind | Fits PC | Notes |
|-----|------|---------|-------
| `qwythos-9b-q8_0` | dense (MTP) | No | **LIVE model** — `Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf`, qwen35 arch + MTP draft heads, ~9.5GB, sharded across all 11 nodes (~6.0 tok/s) |
| `llama-3.3-70b-iq3_xs` | dense | No | 70B dense, RPC layer-piping across 11 nodes |
| `qwen2.5-72b-iq3_m` | dense | No | 72B dense coding/JSON/multilingual, RPC layer-piping |
| `codestral-22b-q8_0` | dense | **Yes** | 22B code specialist, Q8_0 ~23.6GB fits PC directly |
| `deepseek-coder-v2-lite-q4_k_m` | moe | **Yes** | 16B total / 2.4B active MoE; Tier 2 ring target (64 experts ~6/node) |
| `deepseek-r1-distill-qwen-32b-q6_k_l` | dense | No | 32B reasoning model, pushed to node0 SSD |

Each entry has `local` (PC path), `hf_url` (HF resolve URL), `kind`, `fits_pc`, `notes`. `model_download` drives a resumable range-segmented fetch via `code/dl_generic_model.py` (auth from `HF_TOKEN` env or `C:\Models\.hf_token`). **Codestral-22B is the "one more model" downloaded to the PC** (fits directly, no sharding needed). The MTP models (`qwythos-9b-q8_0`, and the dense 70B/72B entries which use `qwen2`/`qwen35` arch) require the MTP build end-to-end — coordinator (`C:\llama.cpp-mtp`) and workers (`ggml-rpc-server`) must both be the MTP tree.

### B.7 PyCUDA install on node0 (golden-image dependency)

- **Why:** the PyCUDA workers `import pycuda` at module load. `phase4_dependencies.sh` does NOT install pycuda/numpy, so it must be present on the template before Phase 9a capture (so the 10 clones inherit it).
- **node0 environment:** Python 3.8.10, pip 20.0.2, CUDA 10.2.300 (`/usr/local/cuda`), numpy 1.18.5 (already present), pycuda absent.
- **Install (non-interactive SSH needs absolute paths; `python3`/`pip3` not on PATH):**
  ```bash
  ssh jetson@192.168.50.150 "export PATH=/usr/local/cuda/bin:/usr/bin:$PATH; \
    export CUDA_ROOT=/usr/local/cuda; \
    /usr/bin/python3 -m pip install --user pycuda==2021.1"
  ```
  Pinned to **2021.1** — the last PyCUDA release supporting CUDA 10.2 / Python 3.8. (Latest pulls a version requiring newer Python/CUDA and fails to compile.)
- **Verify:**
  ```bash
  /usr/bin/python3 -c "import pycuda.autoinit; import pycuda.driver as cuda; \
    print(cuda.Device(0).name())"   # -> NVIDIA Tegra X1
  ```
- **Status:** ✅ Installed and verified on node0. Phase 9a golden-image capture will bake it into all 11 nodes. The TensorFlow 2.4.1 dependency warnings during install are harmless (TF is not used by the cluster).
- **Note:** node0 is the clone template — never purge desktop/packages on it; capture is read-only on the card.

### B.8 Running the MCP server

```powershell
cd C:\Users\marti\Desktop\Cluster\code\mcp
py -3.14 -m cluster_mcp_server      # stdio transport; register in VS Code / Claude Desktop MCP config
```
The `mcp` package is installed under the `py -3.14` launcher (NOT bare `python`). Import check: `py -3.14 -c "import cluster_config, cluster_mcp_server; print('config OK', len(cluster_config.NODE_IPS), 'nodes')"`.

---

## Appendix A — Build Recipe (b56f079e2, RETIRED reference)

> **Status: RETIRED reference build.** The live fleet runs the **MTP build** (`b9886`/`20a04b2`,
> binary `ggml-rpc-server`, CUDA 10.2 + C++14 port) documented in **`MTP CUDA Enablement Work Plan.md`** —
> that is now the authoritative build record for the running cluster. This appendix is kept as a
> **fallback reference** for the non-MTP `rpc-server` path (it is technically valid and was the
> build that ran before the MTP deployment). The MTP build supersedes it for any model that needs
> the `qwen35` architecture or MTP draft heads (i.e. Qwythos-9B and the rest of the live registry).
>
> The recipe below is verified working: the PC `llama-cli.exe` (CPU-only RPC client) connects to
> node0's `rpc-server` (CUDA 10.2 backend) and generates coherent text; if the server is not
> running, the client fails with `Failed to connect to 192.168.50.150:50052` (the compute is
> offloaded to the Jetson's Maxwell GPU — there is no local fallback).

### A.0 Why this specific commit

| Fact | Detail |
|---|---|
| **Pinned commit** | `b56f079e2` (tag `b4418`, "Vulkan: Add device-specific blacklist for coopmat for the AMD proprietary driver (#11074)"), dated 2025-01-04 |
| **Why this commit** | Last commit before `46e3556e0` ("CUDA: add BF16 support"), which introduced `cuda_bf16.h` (requires CUDA 11.0+). JetPack 4.6.1 is permanently locked to CUDA 10.2, so any newer commit fails to compile on the Nano. |
| **RPC wire protocol** | Client (PC) and server (Nano) **MUST** be built from the **exact same commit**. The wire protocol changes between commits. This is why the PC is built from `b56f079e2` too — NOT a newer commit. |
| **Binary name at this commit** | `rpc-server` (in `examples/rpc/`, output at `build/bin/rpc-server`). **NOT** `llama-rpc-server`. The `llama-rpc-server` name only exists in much newer commits (post ~mid-2025 reorg into `tools/rpc/`). |
| **`--mlock` flag** | **Does NOT exist** at this commit. `rpc-server --help` shows only `-H/-p/-m`. Do not pass `--mlock`; it aborts with `error: unknown argument: --mlock`. Memory locking (if desired) must be done via the `mlockall_wrapper` setuid helper instead. |

### A.1 Authoritative Version Manifest (verified on node0)

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

**The critical compiler split (the key discovery of the build):**
- **nvcc 10.2 REQUIRES gcc-8** as its host compiler (`host_config.h` rejects gcc > 8) → nvcc pinned to gcc-8 via `--compiler-bindir /usr/bin/gcc-8`.
- **BUT** the host C/C++ compiler (used to compile `ggml-cpu`, `common`, `rpc-server.cpp`) **MUST be gcc-9**, because gcc-8's `arm_neon.h` is **missing** the `vld1q_u8_x4` and `vld1q_s8_x4` NEON load intrinsics (used by `ggml-cpu-quants.c` / `ggml-cpu-impl.h`; cause `implicit declaration` errors under gcc-8). gcc-9+ provides them.
- **Working combination: nvcc → gcc-8 (bindir), host C/CXX → gcc-9.**

### A.2 The 4 source patches (CUDA 10.2 incompatibilities)

Apply to the checked-out `b56f079e2` source BEFORE configuring. They persist in the
working tree (survive `rm -rf build`).

| # | File | Change | Why |
|---|---|---|---|
| 1 | `ggml/src/ggml-cuda/common.cuh` | `static constexpr __device__ int8_t kvalues_iq4nl` → `static const __device__ int8_t kvalues_iq4nl` | NVCC 10.2 rejects `constexpr` on `__device__` variables. |
| 2 | `ggml/src/ggml-cuda/fattn-common.cuh` | `__builtin_assume(tid < D)` → `GGML_CUDA_ASSUME(tid < D)` | NVCC 10.2 lacks `__builtin_assume`. `GGML_CUDA_ASSUME` is the project's portable macro. |
| 3 | `ggml/src/ggml-cuda/fattn-vec-f16.cuh` | same `__builtin_assume` → `GGML_CUDA_ASSUME` fix | same reason |
| 4 | `ggml/src/ggml-cuda/fattn-vec-f32.cuh` | same `__builtin_assume` → `GGML_CUDA_ASSUME` fix | same reason |

> This is **4 patches**, not the 5 described in the older `667d72846` recipe. The
> `667d72846` recipe needed a `cuda_bf16.h` stub + `queue.push(std::move(msg))` fix;
> at `b56f079e2` those code paths are either absent or already correct. Do NOT apply
> the `667d72846`-era bf16 stub here.

### A.3 Exact working configure + build (node0)

```bash
# On node0 (Jetson Nano, user jetson, IP 192.168.50.150)
cd ~/llama.cpp
git checkout b56f079e2
# ... apply the 4 patches from A.2 ...

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

**Two non-obvious configure gotchas:**
1. **`GGML_NATIVE=OFF` on the command line does NOT override a cached `ON`.** If a prior configure left `GGML_NATIVE:BOOL=ON` in `CMakeCache.txt`, re-running cmake with `-DGGML_NATIVE=OFF` silently keeps `ON`, and the build then tries to auto-detect `-mcpu=cortex-a57+crypto+nodotprod+noi8mm+nosve` — which gcc-8 can't parse. **Fix:** edit the cache directly:
   ```bash
   sed -i 's/^GGML_NATIVE:BOOL=ON/GGML_NATIVE:BOOL=OFF/; s/^GGML_CPU_ARM_ARCH:STRING=/GGML_CPU_ARM_ARCH:STRING=armv8.1-a+nolse/' build/CMakeCache.txt
   ```
   Then re-run the cmake configure above. Confirm: `-- Adding CPU backend variant ggml-cpu: -march=armv8.1-a+nolse`
2. **`armv8.1-a+nolse` is required, not `armv8-a`.** The `vld1q_u8_x4` intrinsic needs the Armv8.1-a instruction set (enabled by `-march=armv8.1-a`). `+nolse` disables the Large System Extensions the Cortex-A57 doesn't have. Plain `-march=armv8-a` leaves the intrinsic undeclared even under gcc-9.

**Resulting binary:** `~/llama.cpp/build/bin/rpc-server` (verified present, ARM aarch64, `ldd` all libs resolved).

### A.4 Launch the RPC server (node0)

> **Why `-m` is mandatory on Jetson:** The Tegra X1 is UMA — there is no discrete VRAM. If `-m` is omitted, `rpc-server` calls `ggml_backend_cuda_get_device_memory`, which returns only the CUDA carveout (~14 MB free, the `NvMapMemFree` figure), NOT unified RAM. The PC client then sees ~14 MB free and assigns the node almost no layers. **Always pass `-m`** to claim a slice of unified RAM.
>
> **Per-node `-m` table (tune to each node's headroom):**
> | Node | Role | GUI/display | `-m` (MB) | Reason |
> |------|------|-------------|-----------|--------|
> | node0 (192.168.50.150) | Nano Zero | kept | **3000** | Shares unified RAM with desktop; smaller buffer avoids OOM |
> | node1–node10 (151–160) | headless workers | stripped (Phase 9b) | **3600** | Max headroom after GUI removed |
> The client shards layers proportionally to each server's `-m`, so node0's smaller value auto-assigns it fewer layers. If you prefer the client-side override instead, omit per-node tuning and pass `--tensor-split 0.85,1,1,1,1,1,1,1,1,1,1` on the PC (Phase 10) — but not both.

```bash
# Kill any stale instance (use a pattern that does NOT match the ssh command itself)
pkill -f 'rpc-serv''er' || true

# Launch detached. NOTE: no --mlock (unsupported at this commit).
# node0 uses -m 3000 (GUI kept); headless workers use -m 3600 (see table above).
setsid nohup ~/llama.cpp/build/bin/rpc-server \
  -H 0.0.0.0 -p 50052 -m 3000 \
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
Starting RPC server on 0.0.0.0:50052, backend memory: 3000 MB
```

> **`pkill` self-match warning:** never run `pkill -f rpc-server` over SSH — the SSH command line contains the string `rpc-server`, so pkill kills its own parent shell. Use a split pattern like `'rpc-serv''er'` (or `[r]pc-server`) to avoid the match.

### A.5 PC orchestrator build (CPU-only RPC client — RETIRED reference)

> **Live PC build is in Phase 1** (`C:\llama.cpp-mtp`, commit `20a04b2`, MTP build producing `llama-cli.exe` + `llama-server.exe`). The steps below describe the retired `b56f079e2` reference client and are kept only as a fallback record.

- Built from the **same commit `b56f079e2`** (RPC protocol parity; keeps the RTX 5060 free for other work during batch submits).
- `GGML_CUDA=OFF`, `GGML_RPC=ON`, MSVC 19.44 (`VsDevCmd.bat -vcvars_ver=14.44`), Ninja generator.
- **2 source patches** (MSVC strictness in this old commit): `common/common.h` and `common/log.cpp` each need `#include <chrono>`.
- Result: `C:\llama.cpp\build\bin\llama-cli.exe` (has `--rpc`, `--flash-attn`, `-cnv`, **and `--mlock`**; NO `-no-cnv`). Note: `--mlock` exists on the **PC client** but NOT on the Nano `rpc-server` (see Appendix A.0).
- Full script: `code/pc_build/build_cpu_rpc.bat`.

### A.6 Smoke test

```powershell
C:\llama.cpp\build\bin\llama-cli.exe `
  -m C:\Models\tiny_test\qwen0.5b-q4km.gguf `
  -p "Hello" -n 20 --rpc 192.168.50.150:50052
```

Output (truncated): `Hello\n\nI'm trying to write a Python program that will open a file in write mode and write some` — coherent generation, ~102 tok/s eval on the Nano.

**If the server is not running:** with the node0 `rpc-server` killed, the same command fails:
```
Failed to connect to 192.168.50.150:50052
C:\llama.cpp\ggml\src\ggml-backend.cpp:1488: GGML_ASSERT(...) failed
```
This shows the PC client has no local compute fallback — the Maxwell GPU on the Nano performs the work.

### A.7 Caveats (known limitations)

- **The commit is older than current llama.cpp** (post-BF16 reorg, new `llama-rpc-server` binary name, many perf improvements). It is used because it is the newest commit that compiles under CUDA 10.2 / JetPack 4.6.1.
- **The Jetson Nano is slow** (~100 tok/s eval for a 0.5B model; a 70B model would be distributed across many nodes but each node is memory- and bandwidth-bound on 1 Gbps Ethernet + UMA LPDDR4).
- **The build workarounds are non-obvious** (gcc-9-host/gcc-8-nvcc split, the `vld1q_u8_x4` intrinsic gap, the CMakeCache `GGML_NATIVE` override, the `armv8.1-a` arch, the missing `--mlock` flag). All are documented above so they are reproducible.
- **`--flash-attn` is supported** by `b56f079e2` on the PC client, but on the Nano CUDA 10.2 backend flash attention may not be beneficial/available for sm_53; test before relying on it for the 70B target.
- **Security:** the RPC server prints an explicit warning that exposing it to an open network is insecure (experimental feature). Bind to a trusted, isolated subnet.

### A.8 Repeatability checklist

- [ ] JetPack 4.6.1 / CUDA 10.2 on the Nano; gcc-8 AND gcc-9 installed.
- [ ] CMake 3.27.9 (not 3.16 apt, not 4.x pip).
- [ ] Commit `b56f079e2` checked out on BOTH node0 and PC.
- [ ] 4 CUDA patches applied on node0 (A.2) BEFORE configure.
- [ ] 2 `<chrono>` patches applied on PC (A.5) BEFORE configure.
- [ ] Configure with gcc-9 host + gcc-8 nvcc bindir + `armv8.1-a+nolse` + `GGML_NATIVE=OFF`.
- [ ] `make -j4` from build root (do NOT kill it — let it finish linking rpc-server).
- [ ] Binary is `rpc-server` (not `llama-rpc-server`); launch WITHOUT `--mlock`.
- [ ] PC client connects via `--rpc 192.168.50.150:50052`.
