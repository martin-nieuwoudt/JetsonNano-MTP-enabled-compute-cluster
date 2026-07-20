# Jetson Nano Cluster Resurrection — Unified Action Plan

**Goal:** 10–12× Jetson Nano (4 GB each, 40–48 GB raw → ~30–38 GB usable) as a star-topology RPC compute swarm, orchestrated from Windows PC via llama.cpp RPC + LiteLLM, surfaced into VS Code via GitHub Copilot custom endpoint.

**Architecture:** Star topology — Windows PC is the Master/Head Node. All Nanos talk directly to Windows in parallel. Model file lives on Windows SSD only; weights are stream-allocated to Nanos at boot. No NFS/SMB needed.

**Model Strategy (recommended):** Gemma 4 12B Q8_0 (~13–14 GB) as primary driver. Leaves ~16–18 GB free cluster memory for KV cache. Alternative: Qwen 2.5 32B Q4_K_M (~20 GB) for heavier generalist tasks.

---

## GLOSSARY

- **L4T (Linux for Tegra):** Proprietary NVIDIA drivers necessary for Jetson hardware acceleration, natively frozen at Ubuntu 18.04.
- **QAT (Quantization-Aware Training):** A model compression methodology simulated during active training to retain reasoning precision within reduced VRAM envelopes.
- **RPC (Remote Procedure Call):** A native engine utilized by llama.cpp to stream-allocate model weights and process tensors across parallel network compute backend nodes.
- **Star-Topology:** A network architecture orchestrating direct, simultaneous connections between a Master Core (Windows PC) and all parallel compute slaves to bypass sequential ring latency.
- **Unified Memory Architecture:** A hardware configuration where physical board RAM is shared simultaneously between the Linux kernel and the GPU without an isolated VRAM pool.

---

## ASSUMPTIONS

- All Jetson Nanos utilize the Maxwell (sm_53) GPU architecture.
- The primary workstation orchestrating the environment operates a Windows operating system containing an SSD.
- The primary workstation has the NVIDIA CUDA Toolkit and Visual Studio installed natively.
- A Gigabit Ethernet switch connects the cluster components to mitigate physical data traffic jams.
- A local NVIDIA RTX 3090 is available and configured via vLLM to serve parallel autocomplete tasks.
- Visual Studio Code acts as the primary integrated development environment utilizing GitHub Copilot extensions.

---

## PHASE 1: OPERATING SYSTEM UPGRADES & GOLDEN MASTER PROVISIONING

### 1.1 Acquire Base Image
- [ ] Download **Qengineering Jetson Nano Ubuntu 20.04 Bare Image** (community-patched L4T + Ubuntu 20.04, no TensorFlow/PyTorch bloat)
- [ ] Alternative if ambitious: Pythops Jetson-Image Builder for fully stripped headless build

### 1.2 Initialize Primary Node
- [ ] Flash the downloaded bare image onto a single SD card (≥32 GB recommended) using BalenaEtcher or Raspberry Pi Imager

### 1.3 Install Build-Time Dependencies (Compiler Chain)
- [ ] `sudo apt update && sudo apt install -y build-essential cmake git pkg-config libopenblas-dev liblapack-dev`
- [ ] Verify CUDA toolkit present: `nvcc --version` (should work on Q-Engineering image)

### 1.4 Compile llama.cpp with RPC + CUDA on Golden Master
- [ ] Clone llama.cpp: `git clone https://github.com/ggerganov/llama.cpp && cd llama.cpp`
- [ ] Build targeting Maxwell (sm_53):
  ```bash
  mkdir build && cd build
  cmake .. -DGGML_CUDA=ON -DGGML_RPC=ON -DCMAKE_CUDA_ARCHITECTURES=53
  cmake --build . --config Release
  ```
- [ ] Verify binary: `./bin/llama-rpc-server --help`

### 1.5 Install Runtime & Optimization Layer
- [ ] Install `haveged` entropy daemon: `sudo apt install -y haveged && sudo systemctl enable haveged`
  - *Prevents headless boot stalls due to insufficient entropy for SSH key generation*
- [ ] Set MAXN power mode: `sudo nvpmodel -m 0`
- [ ] Lock CPU/GPU/EMC clocks at maximum: `sudo jetson_clocks`
- [ ] Create `cluster-init.service` to persist on every boot:
  ```ini
  [Unit]
  Description=Jetson Cluster Init (power, clocks, firewall)
  After=network.target

  [Service]
  Type=oneshot
  ExecStart=/bin/bash -c 'nvpmodel -m 0 && jetson_clocks && ufw allow 50052/tcp'
  RemainAfterExit=yes

  [Install]
  WantedBy=multi-user.target
  ```
- [ ] Enable service: `sudo systemctl daemon-reload && sudo systemctl enable cluster-init.service`

### 1.6 Configure Firewall
- [ ] Allow RPC port through UFW: `sudo ufw allow 50052/tcp`
- [ ] Verify: `sudo ufw status`

### 1.7 Create llama-rpc systemd Service
- [ ] Create `/etc/systemd/system/llama-rpc.service`:
  ```ini
  [Unit]
  Description=Llama.cpp RPC Slave Server
  After=network.target

  [Service]
  Type=simple
  User=jetson
  WorkingDirectory=/home/jetson/llama.cpp/build
  ExecStart=/home/jetson/llama.cpp/build/bin/llama-rpc-server --host 0.0.0.0 --port 50052
  Restart=always
  RestartSec=5

  [Install]
  WantedBy=multi-user.target
  ```
- [ ] Enable: `sudo systemctl daemon-reload && sudo systemctl enable llama-rpc.service`

### 1.8 Sanitize Identity Before Cloning
- [ ] Remove SSH host keys so each clone regenerates unique keys on first boot:
  ```bash
  sudo rm -f /etc/ssh/ssh_host_*
  sudo rm -f /etc/machine-id
  sudo rm -f /var/lib/dbus/machine-id
  ```
- [ ] Clean logs and package cache to minimize image size:
  ```bash
  sudo journalctl --vacuum-time=1s
  sudo apt clean
  ```

### 1.9 Establish Network Template
- [ ] Configure netplan/NetworkManager for DHCP (reservations configured on router, not static IPs in OS)
- [ ] Add Master PC to `/etc/hosts`: `192.168.1.50 master-pc`
- [ ] Verify network is functioning, then power down the node

### 1.10 Disable GUI Environment (LAST STEP — saves ~400 MB RAM per node)
- [ ] Execute: `sudo systemctl set-default multi-user.target`
- [ ] Reboot — GUI will never load again, baseline system RAM footprint drops to ~400–420 MB

### 1.11 Create Golden Master Clone
- [ ] Remove SD card, mount in Windows PC
- [ ] WSL/Git Bash: `sudo dd if=/dev/sdX of=/mnt/c/Users/marti/Desktop/Jetson_22.04_Headless_Master.img bs=4M status=progress`

### 1.12 Deploy Clones
- [ ] Write master image to remaining SD cards (9 for 10-node, 11 for 12-node):
  `sudo dd if=/mnt/c/Users/marti/Desktop/Jetson_22.04_Headless_Master.img of=/dev/sdX bs=4M status=progress`
- [ ] Insert all SD cards into Nanos

---

## PHASE 2: SWARM NETWORK & RPC COMPILATION

### 2.1 Assemble Hardware
- [ ] Insert cloned SD cards into all Nanos, connect to Gigabit Ethernet switch, boot

### 2.2 Define IP Variables
- [ ] Verify each Nano receives correct IP via DHCP reservation: `192.168.1.51` through `192.168.1.62` (accommodating up to 12 nodes)
- [ ] Node 10 (`192.168.1.60`) is initialized purely for continuous compute output, not network failover
- [ ] Label each Nano physically with its IP

### 2.3 SSH Key Setup (Windows → all Nanos)
- [ ] Generate SSH key on Windows if not present: `ssh-keygen -t ed25519`
- [ ] Copy to each Nano: `ssh-copy-id jetson@192.168.1.XX`
- [ ] Verify passwordless SSH works to all nodes

### 2.4 Set Up Ansible Orchestration (WSL2)
- [ ] Install Ansible: `sudo apt update && sudo apt install -y ansible`
- [ ] Create inventory file `~/jetson-cluster/inventory.ini`:
  ```ini
  [nanos]
  192.168.1Pairs.51 ansible_user=jetson
  192.168.1.52 ansible_user=jetson
  192.168.1.53 ansible_user=jetson
  192.168.1.54 ansible_user=jetson
  192.168.1.55 ansible_user=jetson
  192.168.1.56 ansible_user=jetson
  192.168.1.57 ansible_user=jetson
  192.168.1.58 ansible_user=jetson
  192.168.1.59 ansible_user=jetson
  192.168.1.60 ansible_user=jetson
  192.168.1.61 ansible_user=jetson
  192.168.1.62 ansible_user=jetson
  ```
- [ ] Test connectivity: `ansible all -m ping -i inventory.ini`
- [ ] Use Ansible for all subsequent bulk operations (reboot, status checks, binary updates)

### 2.4 Create Automation Script (`setup_nano.sh`)
- [ ] Save on Windows/WSL with array mapping all target IPs and username
- [ ] Script iterates through IP array via SSH and executes:

### 2.5 Execute Remote Installs
- [ ] `sudo apt-get update && sudo apt-get install -y build-essential cmake git libcurl4-openssl-dev`

### 2.6 Map CUDA Environments
- [ ] Append to `~/.bashrc` on every node:
  ```bash
  export PATH=/usr/local/cuda/bin:$PATH
  export LD_LIBRARY_PATH=/usr/local/cuda/lib64:$LD_LIBRARY_PATH
  ```

### 2.7 Compile Collaborative Engines
- [ ] Clone llama.cpp, build directory, compile targeting Maxwell:
  ```bash
  cmake .. -DGGML_CUDA=ON -DGGML_RPC=ON -DCMAKE_CUDA_ARCHITECTURES=53
  cmake --build . --config Release
  ```

### 2.8 Automate Background RPC Services
- [ ] Create systemd service `/etc/systemd/system/llama-rpc.service`:
  ```ini
  [Unit]
  Description=Llama.cpp RPC Slave Server
  After=network.target

  [Service]
  Type=simple
  User=jetson
  WorkingDirectory=/home/jetson/llama.cpp/build
  ExecStart=/home/jetson/llama.cpp/build/bin/llama-rpc-server --host 0.0.0.0 --port 50052
  Restart=always
  RestartSec=5

  [Install]
  WantedBy=multi-user.target
  ```
- [ ] `sudo systemctl daemon-reload && sudo systemctl enable llama-rpc.service && sudo systemctl start llama-rpc.service`

### 2.9 Memory Check Per Node
- [ ] SSH into any Nano, run `free -h`
- [ ] Confirm ~3.0–3.2 GB free per node (OS overhead ~0.8–1.0 GB)

---

## PHASE 3: WINDOWS MASTER ORCHESTRATOR INTEGRATION

### 3.1 Compile Master Client
- [ ] PowerShell/Command Prompt: clone llama.cpp, build with CUDA + RPC:
  ```powershell
  cmake .. -DGGML_CUDA=ON -DGGML_RPC=ON
  cmake --build . --config Release
  ```

### 3.2 Master PC Tooling Checklist
- [ ] Install Ansible in WSL2 for cluster orchestration
- [ ] Install `nmap` and `iperf3` for network diagnostics
- [ ] Install Prometheus + Grafana for cluster monitoring (optional)
- [ ] Create bulk management scripts (reboot all, status all, update binaries)

### 3.2 Acquire Model Assets
- [ ] Download GGUF model files directly to Windows SSD (`C:\Models\`)
- [ ] **Primary:** Gemma 4 12B Q8_0 (~13–14 GB) — sweet spot, leaves 16–18 GB for KV cache
- [ ] **Heavy alternative:** Qwen 2.5 32B Instruct Q4_K_M (~20 GB) — leaves ~12 GB buffer
- [ ] Do NOT place model files or configure network file sharing on the Nanos

### 3.3 Configure LiteLLM Router
- [ ] `pip install litellm`
- [ ] Create `litellm_config.yaml` with model_list:
  ```yaml
  model_list:
    # Autocomplete Model (local RTX 3090 via vLLM)
    - model_name: diffusion-gemma
      litellm_params:
        api_base: "http://localhost:8000/v1"
    # Reasoning Model (Jetson swarm)
    - model_name: gemma-4-swarm
      litellm_params:
        api_base: "http://localhost:8080/v1"
  ```

---

## PHASE 4: VS CODE INTEGRATION & SEQUENCE AUTOMATION

### 4.1 Define Workspace Tasks
- [ ] Create `.vscode/tasks.json` in project root

### 4.2 Map Execution Logic
- [ ] Task 1: Launch sub-clusters via `llama-cli.exe` with `--rpc` flag listing all target IPs
- [ ] For sub-cluster grouping (3 nodes per instance):
  - Nodes 1–3 → port 8080
  - Nodes 4–6 → port 8081
  - Nodes 7–9 → port 8082
  - Nodes 10–12 (if present) → additional ports or join existing groups
- [ ] Task 2: Start LiteLLM router: `litellm --config C:\Path\To\litellm_config.yaml`
- [ ] Task 3: "🚀 Boot Local AI Cockpit" — depends on both, sequence order

### 4.3 Bind GitHub Copilot
- [ ] VS Code → Copilot Chat → Model Selector → Manage Model Providers
- [ ] Add Custom OpenAI-Compatible Endpoint: `http://localhost:4000/v1`
- [ ] API key: any dummy string (e.g., `local-dev`)

### 4.4 Assign Model Pipelines
- [ ] **Inline autocomplete:** VS Code settings → `Copilot Completion Model` → `diffusion-gemma` (3090)
- [ ] **Sidebar chat:** Copilot Chat model picker → `gemma-4-swarm` (Jetson cluster)

### 4.5 Execute Unified Cockpit
- [ ] Press `Ctrl+Shift+B` in VS Code to trigger tasks.json
- [ ] Verify: `curl http://localhost:4000/v1/models`

---

## PHASE 5: RESOURCE MATRICES & DEPLOYMENT VARIABLES

### 5.1 Cluster Resource Metrics

| Resource Metric | 10-Node Value | 12-Node Value | Technical Constraint / Detail |
|-----------------|---------------|---------------|-------------------------------|
| Physical Nodes | 10 | 12 | Unified computing block linked via Gigabit Ethernet switch |
| Raw Physical RAM | 40.0 GB | 48.0 GB | Distributed strictly as 4.0 GB per board without isolated VRAM |
| Base System Overhead | 8.0–10.0 GB | 9.6–12.0 GB | 0.8–1.0 GB per node consumed by headless Linux kernel, network stack, RPC server |
| True Usable VRAM Pool | 30.0–32.0 GB | 36.0–38.4 GB | Net memory for parallel model layer allocation and token processing |

### 5.2 Model Fit Matrix

| Model Specification | Quantization | RAM Required | Free for KV Cache (10-node / 12-node) | Deployment Viability |
|---------------------|--------------|--------------|---------------------------------------|----------------------|
| Gemma 4 12B | 4-bit (QAT / Q4) | ~7.0 GB | ~23 GB / ~29 GB | Optimal — requires only 3 Nanos per full instance |
| Gemma 4 12B | 8-bit (Q8_0 / IQ8_NL) | 13.0–14.0 GB | ~16–18 GB / ~22–24 GB | **Sweet Spot** — 99.5% unquantized accuracy |
| Gemma 4 12B | 16-bit Unquantized | 24.0–26.0 GB | ~5–6 GB / ~11–12 GB | Marginally Viable — tight context buffer, OOM risk |
| Qwen 2.5 32B Instruct | 4-bit (Q4_K_M) | 20.2 GB | ~10–12 GB / ~16–18 GB | Highly Viable — elite open-weights generalist |
| Command R 35B | 4-bit (Q4_K_M) | 22.5 GB | ~7.5–9.5 GB / ~13.5–15.5 GB | Highly Viable — RAG-optimized, reduced token footprint |

---

## CONCLUSION

By upgrading an array of 10–12 legacy Jetson Nanos to a headless, natively compiled Ubuntu 22.04 base and binding them via an RPC Star-Topology framework, a highly modular 30–38 GB unified memory pool is systematically constructed. Orchestrated by a Windows Master Core dynamically managing parameter allocation and LiteLLM task routing, this architecture facilitates the execution of dense 32B+ parameter models directly through native GitHub Copilot IDE interfaces while circumventing primary single-card VRAM limitations.

---

## COUNTER-ARGUMENT

While the distributed Maxwell GPU framework mathematically accommodates parameter requirements far exceeding a single standard GPU, the inherent bandwidth constraints dictated by Gigabit Ethernet protocols establish an unavoidable structural bottleneck for input/output transmission. This Star-Topology framework demands stringent OS maintenance across 11–13 discrete nodes (10–12 Nanos + Windows master), risking higher aggregate downtime potentials compared to executing scaled models via high-throughput cloud endpoints or standardized high-VRAM dual-GPU hardware configurations.

---

## DIALECTICAL SYNTHESIS

The 10–12 node localized RPC cluster functions as an architecturally valid and highly cost-efficient mechanism for deploying large parameter arrays locally, systematically transforming low-power edge compute units into a viable 32B logic engine without incurring subscription telemetry. However, this configuration remains permanently bound by ethernet transmission capacities, dictating that the reasoning depth achieved by deploying immense models must mathematically outweigh the processing latency imposed by persistent network tensor broadcasting.

---

## REFERENCE — KEY COMMANDS

```powershell
# Windows: launch single full-cluster instance (all Nanos, one model)
.\bin\Release\llama-cli.exe --model C:\Models\gemma-4-12b-it-Q8_0.gguf --rpc 192.168.1.51:50052,192.168.1.52:50052,192.168.1.53:50052,192.168.1.54:50052,192.168.1.55:50052,192.168.1.56:50052,192.168.1.57:50052,192.168.1.58:50052,192.168.1.59:50052,192.168.1.60:50052 --ctx-size 8192 --server --port 8080

# Windows: launch 3 sub-clusters (3× independent model instances, 10-node)
start .\bin\Release\llama-cli.exe --model C:\Models\gemma-4-12b-Q4_0.gguf --rpc 192.168.1.51:50052,192.168.1.52:50052,192.168.1.53:50052 --server --port 8080
start .\bin\Release\llama-cli.exe --model C:\Models\gemma-4-12b-Q4_0.gguf --rpc 192.168.1.54:50052,192.168.1.55:50052,192.168.1.56:50052 --server --port 8081
start .\bin\Release\llama-cli.exe --model C:\Models\gemma-4-12b-Q4_0.gguf --rpc 192.168.1.57:50052,192.168.1.58:50052,192.168.1.59:50052,192.168.1.60:50052 --server --port 8082

# Windows: launch 4 sub-clusters (12-node, 3 nodes each)
start .\bin\Release\llama-cli.exe --model C:\Models\gemma-4-12b-Q4_0.gguf --rpc 192.168.1.51:50052,192.168.1.52:50052,192.168.1.53:50052 --server --port 8080
start .\bin\Release\llama-cli.exe --model C:\Models\gemma-4-12b-Q4_0.gguf --rpc 192.168.1.54:50052,192.168.1.55:50052,192.168.1.56:50052 --server --port 8081
start .\bin\Release\llama-cli.exe --model C:\Models\gemma-4-12b-Q4_0.gguf --rpc 192.168.1.57:50052,192.168.1.58:50052,192.168.1.59:50052 --server --port 8082
start .\bin\Release\llama-cli.exe --model C:\Models\gemma-4-12b-Q4_0.gguf --rpc 192.168.1.60:50052,192.168.1.61:50052,192.168.1.62:50052 --server --port 8083

# LiteLLM
litellm --config C:\Path\To\litellm_config.yaml

# Health checks
curl http://localhost:8080/v1/models
curl http://localhost:4000/v1/models
```
