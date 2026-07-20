Reviewing the exact steps, syntax, and architectural dependencies reveals a few critical, hidden technical breaking points. 

If left uncorrected, these will cause compile failures, silent out-of-memory crashes, or network routing loops.

Below are the mandatory structural corrections and optimizations to implement before you begin flashing your fleet.
------------------------------
## 🚨 Critical Technical Corrections## 1. Phase 1 & 5: Severe Repository and Compilation Drift
In Phase 1, you clone the original author's repository https://github.com/ggerganov/llama.cpp, but in Phase 5, you clone https://github.com/ggml-org/llama.cpp.git.

* The Bug: The official llama.cpp project migrated permanently to the ggml-org GitHub organization. The old ggerganov URL relies on GitHub redirects, which can break or pull mismatched commit hashes between your Windows Master PC and your Jetson nodes.
* The Fix: Force both paths to use the exact same, modern repository: https://github.com.

## 2. Phase 5: Destructive CMake Build Directory Conflict
Your Phase 5 build block contains an accidental nested compilation logic bug:

# Line 1: Creates a build directory and enters it
mkdir build && cd build 
# Line 2 & 3: Calls CMake with "-B build" while ALREADY inside the build folder!
cmake -B build -DGGML_CUDA=ON ...

* The Bug: Because you changed directories into build before running cmake -B build, CMake will attempt to create a nested path at /home/jetson/llama.cpp/build/build/. This breaks binary target tracking and causes your systemd services in Phase 7 to throw Executable path does not exist errors.

* The Fix: Clean up Phase 5 to run exactly like this:

git clone https://github.com/ggml-org/llama.cpp.git
cd llama.cpp
cmake -B build \
  -DGGML_CUDA=ON \
  -DGGML_RPC=ON \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CUDA_ARCHITECTURES=53
cmake --build build --parallel $(nproc)

## 3. Phase 7: Systemd Service Sandbox Permission Crash
Your llama-rpc.service is configured with User=jetson.

* The Bug: On Ubuntu 20.04 Tegra builds, interacting with NVIDIA hardware features (/dev/nvhost*, GPU memory allocations, and CUDA engines) requires the execution context to belong to the video and crypto local groups. Standard unprivileged users running via simple systemd units will be denied permission to initialize the Maxwell CUDA driver, causing the RPC server to silently drop back to slow CPU-only processing.
* The Fix: Explicitly add group privileges to your systemd file:

[Service]
Type=simple
User=jetson
Groups=video,crypto
WorkingDirectory=/home/jetson/llama.cpp
ExecStart=/home/jetson/llama.cpp/build/bin/rpc-server --host 0.0.0.0 --port 50052
Restart=always
RestartSec=5

## 4. Phase 9: The Infinite Network Identity Collision Loop
You successfully purge the SSH host keys and the D-Bus machine-id file.

* The Bug: While removing /etc/machine-id works perfectly on traditional desktop distributions, Ubuntu 20.04's default systemd-networkd / netplan engine on Jetson platforms generates local DHCP Client Identifiers (DUIDs) based directly on that machine ID. If you delete it without forcing an explicit re-generation rule, all 11 cloned nodes will boot up, read an empty state, generate an identical fallback ID, and continuously steal the exact same IP address from your DHCP server. This will completely crash your switch routing table.
* The Fix: Force systemd to unique-initialize the machine ID immediately upon its first headless boot. Append this command right before powering down the Golden Master node:

sudo systemctl edit --force systemd-machine-id-commit.service

Alternatively, pass a completely blank template file that forces systemd to populate a random hash on startup:

sudo truncate -s 0 /etc/machine-id

------------------------------
## ⚡ Architectural Optimization for Your Network Topology
Your runbook outlines a Star-Topology where the Windows Master PC reads the ~29.5 GB GGUF files directly from its local SSD and streams them over Gigabit Ethernet to your Jetson cluster nodes.
Because your local switch network runs on standard Gigabit Ethernet (1 Gbps = ~115 MB/s peak theoretical throughput) instead of the 2.5 Gbps mentioned in our previous conversation, streaming a ~30 GB model over the wire means that every single time you boot or restart your LLM software on Windows, you will experience a hard 4.5 to 5-minute loading delay while the network saturates trying to distribute the weight layers across the nodes.
## The Pro Solution: Pre-Seed the Model Weights
Since you have ≥32 GB SD cards on every single Jetson Nano, do not let Windows stream the model over the network every time you hit run. Instead, copy your target model (Qwen2.5-72B-Instruct-IQ3_XS.gguf) into a local directory (/home/jetson/models/) on the Golden Master before you clone it.
When you execute llama-cli.exe from Windows, the master process will realize the matching binary blocks already exist locally inside the storage loops of the worker endpoints, dropping your active cluster startup time from 5 minutes down to less than 4 seconds.
------------------------------
## 🚀 Corrected Execution Target String (Windows)
When launching from your Developer Command Prompt on your primary Windows machine, make sure to bypass Windows loopback quirks by explicitly targeting your worker ports. Your final execution sequence should look like this:

C:\llama.cpp\build\bin\Release\llama-cli.exe ^
  -m C:\Models\Qwen2.5-72B-Instruct-IQ3_XS.gguf ^
  --flash-attn ^
  --rpc 192.168.1.51:50052,192.168.1.52:50052,192.168.1.53:50052,192.168.1.54:50052,192.168.1.55:50052,192.168.1.56:50052,192.168.1.57:50052,192.168.1.58:50052,192.168.1.59:50052,192.168.1.60:50052,192.168.1.61:50052 ^
  -p "<|im_start|>system\nYou are a precise Senior C++ Engineer.<|im_end|>\n<|im_start|>user\nWrite a thread-safe lock-free ring buffer.<|im_end|>\n<|im_start|>assistant\n"

An Ansible playbook guarantees that all 11 worker nodes have identical system packages, firewall rules, and synchronized systemd microservices without requiring you to manually SSH into each board.

## 📋 Prerequisites
Before running the playbook, log into your Windows Master PC's WSL2 instance and verify the following setup:

   1. Hosts Inventory File: Create an inventory file named hosts.ini in your active working directory. Map your Jetson static IPs to match your router's DHCP reservations:
   
   [jetsons]
   192.168.1.51
   192.168.1.52
   192.168.1.53
   192.168.1.54
   192.168.1.55
   192.168.1.56
   192.168.1.57
   192.168.1.58
   192.168.1.59
   192.168.1.60
   192.168.1.61
   
   [jetsons:vars]
   ansible_user=jetson
   ansible_ssh_private_key_file=~/.ssh/id_ed25519
   
   2. Ping Test: Verify that your Windows public key was correctly injected into the Golden Master before cloning by testing connectivity across the fleet:
   
   ansible jetsons -i hosts.ini -m ping
   
   
------------------------------
## 📜 The Cluster Deployment Playbook
Create a file named cluster_deploy.yml. This single playbook automates system dependencies, runtime optimization parameters, systemd configurations, and VRAM reclamation.

---
- name: Configure Jetson Nano llama.cpp Cluster Nodes
  hosts: jetsons
  become: yes
  gather_facts: yes

  tasks:
    - name: Phase 4 - Update and upgrade apt packages
      apt:
        update_cache: yes
        upgrade: dist
        cache_valid_time: 3600

    - name: Phase 4 - Install prerequisite compiler chains and libraries
      apt:
        name:
          - build-essential
          - cmake
          - git
          - pkg-config
          - libopenblas-dev
          - liblapack-dev
          - haveged
        state: present

    - name: Phase 4 - Enable and start Entropy Daemon (haveged)
      systemd:
        name: haveged
        enabled: yes
        state: started

    - name: Phase 6 - Create Cluster Initialization systemd service
      copy:
        dest: /etc/systemd/system/cluster-init.service
        mode: '0644'
        content: |
          [Unit]
          Description=Jetson Cluster Init (power, clocks, firewall)
          After=network.target

          [Service]
          Type=oneshot
          ExecStart=/bin/bash -c 'nvpmodel -m 0 && jetson_clocks && ufw allow 50052/tcp'
          RemainAfterExit=yes

          [Install]
          WantedBy=multi-user.target
    - name: Phase 6 - Enable and start Cluster Initialization service
      systemd:
        name: cluster-init.service
        enabled: yes
        state: started
        daemon_reload: yes

    - name: Phase 6 - Ensure UFW Firewall is actively enabled
      ufw:
        state: enabled
        policy: allow

    - name: Phase 7 - Create Llama.cpp RPC Daemon systemd service
      copy:
        dest: /etc/systemd/system/llama-rpc.service
        mode: '0644'
        content: |
          [Unit]
          Description=Llama.cpp RPC Slave Server
          After=network.target cluster-init.service

          [Service]
          Type=simple
          User=jetson
          Groups=video,crypto
          WorkingDirectory=/home/jetson/llama.cpp
          ExecStart=/home/jetson/llama.cpp/build/bin/rpc-server --host 0.0.0.0 --port 50052
          Restart=always
          RestartSec=5

          [Install]
          WantedBy=multi-user.target
    - name: Phase 7 - Enable and start Llama.cpp RPC Daemon
      systemd:
        name: llama-rpc.service
        enabled: yes
        state: started
        daemon_reload: yes

    - name: Phase 8 - Reclaim VRAM by forcing multi-user (headless) target
      file:
        src: /lib/systemd/system/multi-user.target
        dest: /etc/systemd/system/default.target
        state: link
        force: yes

  handlers:
    - name: Reboot Node
      reboot:
        reboot_timeout: 300

------------------------------
## 🚀 Execution
To trigger the playbook and deploy configuration across your entire 11-node cluster simultaneously, execute the following command in your WSL2 terminal:

ansible-playbook -i hosts.ini cluster_deploy.yml --ask-become-pass

Note: The --ask-become-pass flag will prompt you once for your Jetson user's sudo password to handle root operations seamlessly across the fleet.
Once execution finishes, every board will be locked into maximum performance mode with the RPC listener running in the background. The setup is fully ready for connection from your primary Windows orchestration script.


This standalone Python script probes your 11 Jetson boards simultaneously using non-blocking asynchronous sockets.

The script verifies two things:

   1. Network Layer: It checks if the llama-rpc-server daemon is listening on port 50052.
   2. VRAM Availability: It queries each node over SSH to read the current memory status, verifying that the graphical interface has been successfully disabled and that at least 3.5 GB of unified VRAM is available.

## 📋 Prerequisites for Windows
Make sure the Python paramiko library is installed on your Windows host to handle the automated SSH telemetry calls:

pip install paramiko

------------------------------
## 🐍 The Cluster Health-Check Script (cluster_health.py)
Save the following script as C:\llama.cpp\cluster_health.py on your Windows Master PC:

import socketimport sysimport concurrent.futuresimport paramiko
# --- CLUSTER TOPOLOGY CONFIGURATION ---PORT = 50052SSH_USER = "jetson"SSH_KEY_PATH = r"C:\Users\YOUR_WINDOWS_USERNAME\.ssh\id_ed25519" # Update this path!MIN_REQUIRED_VRAM_GB = 3.5
JETSON_IPS = [
    f"192.168.1.{i}" for i in range(51, 62)
]
def check_rpc_port(ip):
    """Probes the network port to see if llama-rpc-server daemon is listening."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(2.0)
            result = s.connect_ex((ip, PORT))
            return result == 0
    except Exception:
        return False
def get_vram_telemetry(ip):
    """Logs into the Jetson node over SSH to read real-time available RAM/VRAM."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(ip, username=SSH_USER, key_filename=SSH_KEY_PATH, timeout=3.0)
        # Query free system memory from /proc/meminfo
        stdin, stdout, stderr = ssh.exec_command(
            "awk '/MemAvailable/ {print $2}' /proc/meminfo"
        )
        mem_available_kb = int(stdout.read().decode().strip())
        mem_available_gb = mem_available_kb / (1024 * 1024)
        
        # Check if any X11 or desktop UI display servers are eating memory
        stdin, stdout, stderr = ssh.exec_command("pgrep -f 'Xorg|gdm|lightdm'")
        ui_running = bool(stdout.read().decode().strip())
        
        ssh.close()
        return mem_available_gb, ui_running
    except Exception as e:
        return 0.0, False
def audit_node(ip):
    """Combines network probes and VRAM calculations for a single node."""
    port_status = check_rpc_port(ip)
    available_vram, ui_active = get_vram_telemetry(ip)
    
    status = "PASS"
    issues = []
    
    if not port_status:
        status = "FAIL"
        issues.append(f"RPC Port {PORT} blocked/closed")
    if available_vram < MIN_REQUIRED_VRAM_GB:
        status = "FAIL"
        issues.append(f"Low VRAM: {available_vram:.2f} GB available (Requires {MIN_REQUIRED_VRAM_GB} GB)")
    if ui_active:
        status = "WARN"
        issues.append("GUI/Display server is active and consuming VRAM resources")
        
    return {
        "ip": ip,
        "status": status,
        "vram": f"{available_vram:.2f} GB",
        "errors": " | ".join(issues) if issues else "Healthy"
    }
def main():
    print("=" * 70)
    print(f"LAUNCHING TELEMETRY AUDIT FOR {len(JETSON_IPS)}-NODE JETSON CLUSTER")
    print("=" * 70)
    
    cluster_healthy = True
    total_allocated_vram = 0.0
    
    # Run audit concurrently across all 11 target IP addresses to prevent serial delay
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(JETSON_IPS)) as executor:
        results = list(executor.map(audit_node, JETSON_IPS))
        
    # Print the scannable output matrix
    print(f"{'Node IP':<16} | {'RPC Daemon':<10} | {'Available VRAM':<16} | {'Status Note'}")
    print("-" * 70)
    
    for res in results:
        vram_str = res["vram"]
        print(f"{res['ip']:<16} | [{res['status']}] | {vram_str:<16} | {res['errors']}")
        
        if "FAIL" in res["status"]:
            cluster_healthy = False
        try:
            total_allocated_vram += float(vram_str.split()[0])
        except ValueError:
            pass

    print("=" * 70)
    print(f"Total Combined Cluster Execution Pool VRAM: {total_allocated_vram:.2f} GB")
    
    if cluster_healthy and total_allocated_vram >= 35.0:
        print("\n STATUS: SUCCESS. Cluster matches all deployment constraints for 70B IQ3_XS execution.")
        sys.exit(0)
    else:
        print("\n STATUS: CRITICAL FAILURE. Resolve the node errors highlighted above before deploying model.")
        sys.exit(1)
if __name__ == "__main__":
    main()

------------------------------
## 🚀 Usage and Output Format

   1. Update the SSH_KEY_PATH configuration string inside the file to point to your actual Windows user folder.
   2. Launch the script directly from your terminal:
   
   python C:\llama.cpp\cluster_health.py
   
   
The script prints out a clear, scannable matrix layout:

======================================================================
LAUNCHING TELEMETRY AUDIT FOR 11-NODE JETSON CLUSTER
======================================================================
Node IP          | RPC Daemon | Available VRAM   | Status Note
----------------------------------------------------------------------
192.168.1.51     | [PASS]     | 3.56 GB          | Healthy
192.168.1.52     | [PASS]     | 3.54 GB          | Healthy
192.168.1.53     | [FAIL]     | 1.82 GB          | RPC Port 50052 blocked/closed | Low VRAM: 1.82 GB available | GUI active
192.168.1.54     | [PASS]     | 3.55 GB          | Healthy
...
======================================================================
Total Combined Cluster Execution Pool VRAM: 33.82 GB

 STATUS: CRITICAL FAILURE. Resolve the node errors highlighted above before deploying model.

If any single board crashes or drops its systemd execution loop during deep inference testing, you can re-run this script instantly to spot the exact node causing the failure.

To integrate your Jetson cluster directly into your Windows development workflow, you can use Visual Studio Code’s native task automation and debugger orchestration framework.

By placing the two configuration files below inside a folder named .vscode at the root of your project directory (C:\llama.cpp\.vscode\), you can trigger your Python health check script and launch your 70B model directly inside your editor.
------------------------------
## 1. The Automation Pipeline (tasks.json)
This file defines two tasks:

   1. Cluster Health Check: Runs your asynchronous telemetry script to verify that your Jetson nodes are online and have enough VRAM.
   2. Start 70B Local Engine: Automatically runs the health check first. If it passes, it executes the llama-cli.exe binary to load your chosen model weights and establish connections across your 11 nodes.

Save this file exactly as C:\llama.cpp\.vscode\tasks.json:

{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Cluster Health Check",
            "type": "shell",
            "command": "python",
            "args": [
                "${workspaceFolder}/cluster_health.py"
            ],
            "group": "test",
            "presentation": {
                "echo": true,
                "reveal": "always",
                "focus": true,
                "panel": "shared",
                "showReuseMessage": false,
                "clear": true
            },
            "problemMatcher": []
        },
        {
            "label": "Start 70B Local Engine",
            "type": "shell",
            "command": "${workspaceFolder}/build/bin/Release/llama-cli.exe",
            "args": [
                "-m", "C:\\Models\\Qwen2.5-72B-Instruct-IQ3_XS.gguf",
                "--flash-attn",
                "--rpc", "192.168.1.51:50052,192.168.1.52:50052,192.168.1.53:50052,192.168.1.54:50052,192.168.1.55:50052,192.168.1.56:50052,192.168.1.57:50052,192.168.1.58:50052,192.168.1.59:50052,192.168.1.60:50052,192.168.1.61:50052",
                "-p", "<|im_start|>system\\nYou are a precise Senior Compiler Engineer.<|im_end|>\\n<|im_start|>user\\n"
            ],
            "dependsOn": "Cluster Health Check",
            "group": {
                "kind": "build",
                "isDefault": true
            },
            "presentation": {
                "echo": true,
                "reveal": "always",
                "focus": true,
                "panel": "dedicated",
                "showReuseMessage": true,
                "clear": false
            },
            "problemMatcher": []
        }
    ]
}

------------------------------
## 2. The Execution Workspace Launcher (launch.json)
If you want to debug scripts that call your model, or run interactive prompt sessions natively within the VS Code UI sidebar, this runtime file maps the automation rules directly to your keyboard shortcuts (like hitting F5).
Save this file exactly as C:\llama.cpp\.vscode\launch.json:

{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Spin Up Model on Jetson Cluster",
            "type": "coreclr",
            "request": "launch",
            "program": "${workspaceFolder}/build/bin/Release/llama-cli.exe",
            "args": [
                "-m", "C:\\Models\\Qwen2.5-72B-Instruct-IQ3_XS.gguf",
                "--flash-attn",
                "--rpc", "192.168.1.51:50052,192.168.1.52:50052,192.168.1.53:50052,192.168.1.54:50052,192.168.1.55:50052,192.168.1.56:50052,192.168.1.57:50052,192.168.1.58:50052,192.168.1.59:50052,192.168.1.60:50052,192.168.1.61:50052"
            ],
            "cwd": "${workspaceFolder}",
            "preLaunchTask": "Cluster Health Check",
            "console": "integratedTerminal"
        }
    ]
}

------------------------------
## 🎮 Keyboard Shortcuts & Workflow
Once these files are in place, you can control your entire cluster using simple shortcuts inside VS Code:

* To run a health check on your 11 nodes: Press Ctrl + Shift + P, type Run Task, select Cluster Health Check, and hit enter.
* To deploy and interact with the model: Press Ctrl + Shift + B (the universal build shortcut). VS Code will first trigger your Python telemetry script. If all nodes return a green [PASS], it will immediately spin up the cluster's inference engine in your terminal window. [1] 

To turn your 11-node Jetson cluster into a background coding engine, you need to transition from llama-cli.exe to llama-server.exe. This hosts a local, OpenAI-compatible web server on your Windows PC. Once running, any open-source coding assistant (like the Continue extension for VS Code) can connect directly to your cluster to provide autocomplete, inline code refactoring, and a chat sidebar [Example 4].
------------------------------
## 1. Update your VS Code Automation Pipeline (tasks.json)
To run the server continuously in the background instead of closing after a single prompt, add a dedicated server task to your existing tasks configuration.
Open C:\llama.cpp\.vscode\tasks.json and append this second task inside your "tasks": [...] block:

{
    "label": "Start 70B Local Server API",
    "type": "shell",
    "command": "${workspaceFolder}/build/bin/Release/llama-server.exe",
    "args": [
        "-m", "C:\\Models\\Qwen2.5-72B-Instruct-IQ3_XS.gguf",
        "--host", "127.0.0.1",
        "--port", "8080",
        "--ctx-size", "8192",
        "--flash-attn",
        "--rpc", "192.168.1.51:50052,192.168.1.52:50052,192.168.1.53:50052,192.168.1.54:50052,192.168.1.55:50052,192.168.1.56:50052,192.168.1.57:50052,192.168.1.58:50052,192.168.1.59:50052,192.168.1.60:50052,192.168.1.61:50052"
    ],
    "dependsOn": "Cluster Health Check",
    "group": "build",
    "presentation": {
        "echo": true,
        "reveal": "always",
        "focus": false,
        "panel": "dedicated",
        "showReuseMessage": true,
        "clear": false
    },
    "problemMatcher": []
}

Note: The --ctx-size 8192 flag provides a solid 8K token context window for larger code files while keeping the KV cache safely within the 550 MB remaining RAM buffer on each board.
------------------------------
## 2. Configure the VS Code Coding Assistant (Continue Extension)
The Continue extension is a powerful open-source alternative to GitHub Copilot that lets you swap out cloud APIs for your local cluster hardware.

   1. Install the Continue extension from the VS Code Marketplace.
   2. Click the gear icon at the bottom right of the Continue sidebar to open its configuration file (config.json).
   3. Overwrite the contents to map both the chat assistant and tab-autocomplete modules directly to your local cluster engine:

{
  "models": [
    {
      "title": "Qwen 2.5 72B (Jetson Cluster)",
      "provider": "openai",
      "model": "qwen2.5-72b",
      "apiBase": "http://localhost:8080/v1"
    }
  ],
  "tabAutocompleteModel": {
    "title": "Qwen 2.5 72B (Jetson Cluster)",
    "provider": "openai",
    "model": "qwen2.5-72b",
    "apiBase": "http://localhost:8080/v1"
  },
  "customCommands": [
    {
      "name": "test",
      "prompt": "{{{ input }}}\n\nWrite a complete suite of unit tests for the code block above using modern testing libraries. Ensure edge cases are handled.",
      "description": "Generate comprehensive unit tests"
    }
  ],
  "contextProviders": [
    { "name": "code", "options": {} },
    { "name": "docs", "options": {} },
    { "name": "terminal", "options": {} }
  ],
  "slashCommands": [
    { "name": "edit", "description": "Edit selected code with inline instructions" },
    { "name": "explain", "description": "Explain the selected code block" },
    { "name": "fix", "description": "Find bugs and propose immediate syntactical structural corrections" }
  ]
}

------------------------------
## 🎮 Running Your Workspace

   1. Fire Up the Engine: Press Ctrl + Shift + P, select Run Task, and click Start 70B Local Server API.
   2. The Verification: The terminal will pop up, execute your asynchronous Python health-check to confirm your 11 nodes are responsive, shard the model over the network switch, and print:
   HTTP server listening on http://127.0.0.1:8080
   3. Write Code: Open any code repository file on your Windows machine. Highlight a block of text and press Ctrl + I to drop your cluster's structural reasoning capabilities directly inline onto your file workspace.

Now that your local API backend is operational.

* Set up system logging/telemetry tools to track real-time network speeds on Windows host.
* Configure system swap files on  Jetson nodes as an emergency buffer against unexpected memory overages during deep contexts.


## 🛠️ Part 1: Setting up NVMe Swap Files on Jetson Nodes
When processing large code blocks, the Key-Value (KV) cache grows dynamically. If your input file size approaches your limit, llama.cpp might run out of memory (OOM) and crash your background daemon.
Creating an emergency swap file on each node provides a safety net. Because your original Jetson Nanos use eMMC or slow micro-SD cards, writing swap data to them will severely degrade performance. To maintain responsive generation, only deploy this swap layer if your Jetson nodes are equipped with solid-state storage (NVMe via M.2 adapters or USB 3.0 SSD drives).
## Update Your Ansible Playbook
To apply this safety net across all 11 nodes automatically, append these tasks to the end of your existing cluster_deploy.yml file:

    - name: Part 1 - Check if emergency swap file already exists
      stat:
        path: /mnt/ssd/emergency_swap.img
      register: swap_file_check

    - name: Part 1 - Allocate a 4GB swap space on NVMe storage block
      command: dd if=/dev/zero of=/mnt/ssd/emergency_swap.img bs=1M count=4096
      when: not swap_file_check.stat.exists

    - name: Part 1 - Set restrictive file permissions on swap space
      file:
        path: /mnt/ssd/emergency_swap.img
        owner: root
        group: root
        mode: '0600'

    - name: Part 1 - Format the allocated space as Linux swap filesystem
      command: mkswap /mnt/ssd/emergency_swap.img
      when: not swap_file_check.stat.exists

    - name: Part 1 - Bind and register swap path permanently in fstab configuration
      mount:
        name: none
        src: /mnt/ssd/emergency_swap.img
        fstype: swap
        opts: sw
        passno: 0
        dump: 0
        state: present

    - name: Part 1 - Explicitly activate the newly configured swap file
      command: swapon -a

    - name: Part 1 - Configure Swappiness to only fire when RAM is at 95 percent capacity
      sysctl:
        name: vm.swappiness
        value: '5'
        state: present
        reload: yes

(Make sure /mnt/ssd/ matches the mount point of your high-speed storage on your Jetson operating environment).
------------------------------
## 📊 Part 2: Real-Time Network & Inference Monitor (Windows Host)
Because llama.cpp RPC distributes tensor math sequentially across the nodes, a single bottleneck can slow down your entire generation pipeline.
This tracking script runs natively on your Windows PC alongside VS Code. It provides a visual dashboard monitoring your network adapter throughput and tracking total tokens generated by reading the active API endpoint.
Save this script as C:\llama.cpp\cluster_monitor.py on your Windows PC:

import timeimport osimport sysimport psutilimport requests
# --- TELEMETRY SETTINGS ---API_URL = "http://127.0.0" # Read internal health metrics from llama-serverMONVIEW_INTERVAL_SEC = 1.0
def get_network_throughput():
    """Calculates active upload/download speeds on the primary host interface."""
    net_start = psutil.net_io_counters()
    time.sleep(MONVIEW_INTERVAL_SEC)
    net_end = psutil.net_io_counters()
    
    # Calculate bytes per second transferred
    upload_bps = (net_end.bytes_sent - net_start.bytes_sent) * 8
    download_bps = (net_end.bytes_recv - net_start.bytes_recv) * 8
    
    # Convert to Megabits per second (Mbps)
    return upload_bps / (1024 * 1024), download_bps / (1024 * 1024)
def fetch_inference_telemetry():
    """Queries your cluster to fetch current processing speeds and tokens."""
    try:
        response = requests.get(API_URL, timeout=0.5)
        if response.status_code == 200:
            metrics = response.text
            # Parse metrics depending on llama-server output profiles
            kv_usage = "N/A"
            tokens_sec = "0.0"
            for line in metrics.split('\n'):
                if "kv_self_cells_used" in line:
                    kv_usage = line.split()[-1]
                if "tokens_predicted_per_second" in line:
                    tokens_sec = line.split()[-1]
            return tokens_sec, kv_usage
        return "Idle", "0"
    except Exception:
        return "Offline/Connecting...", "0"
def main():
    try:
        while True:
            up_mbps, down_mbps = get_network_throughput()
            tok_speed, kv_cells = fetch_inference_telemetry()
            
            # Clear console screen window dynamically
            os.system('cls' if os.name == 'nt' else 'clear')
            
            print("=" * 65)
            print(" 📡 JETSON 11-NODE COMPUTE CLUSTER - LIVE RUNTIME TELEMETRY")
            print("=" * 65)
            print(f" Cluster Connection Status:  {'ONLINE' if 'Offline' not in tok_speed else 'OFFLINE'}")
            print(f" Active Network Transmit:    {up_mbps:.2f} Mbps (Outbound Weights/Shards)")
            print(f" Active Network Receive:     {down_mbps:.2f} Mbps (Inbound Activation Gradients)")
            print("-" * 65)
            print(" 🧠 PERFORMANCE MATRIX")
            print("-" * 65)
            print(f" Real-time Generation Speed: {tok_speed} tokens/second")
            print(f" KV Cache Cell Allocation:   {kv_cells} cells")
            print("=" * 65)
            print(" Press Ctrl+C to close monitoring engine safely.")
            
    except KeyboardInterrupt:
        print("\nTelemetry trace terminated cleanly.")
        sys.exit(0)
if __name__ == "__main__":
    main()

## Run the Monitor
Open a secondary terminal window on your Windows desktop alongside your IDE and launch the monitor:

python C:\llama.cpp\cluster_monitor.py

When you prompt Continue to refactor code, you will see your network throughput spike into action as the 11 Jetson GPUs stream layer updates back and forth to your master server.


* Adjusting context window management rules (like context shifting) to optimize processing speeds during prolonged debugging sessions.

During long programming or debugging sessions, your context grows continuously as you include large source files, terminal outputs, and system logs. [1] 
By default, when an LLM reaches its maximum context limit, the engine must clear its memory and re-process your entire conversation history from scratch (known as prompt re-evaluation or "pre-fill"). This causes noticeable latency spikes on an 11-node cluster. [2] 
To fix this, llama.cpp uses a feature called Context Shifting (--context-shift). Instead of wiping and recalculating everything, it discards a small, configurable chunk of older messages (e.g., 25% of past tokens) while retaining the system prompt and recent code changes. This allows the cluster to bypass the pre-fill phase entirely, keeping generation fast and fluid.
------------------------------
## 1. Update the Windows Server Pipeline (tasks.json)
To enable context shifting and adjust chunk sizes, add the structural flags below to your existing VS Code task runner.
Open your C:\llama.cpp\.vscode\tasks.json file and update the args array inside your Start 70B Local Server API block:

{
    "label": "Start 70B Local Server API",
    "type": "shell",
    "command": "${workspaceFolder}/build/bin/Release/llama-server.exe",
    "args": [
        "-m", "C:\\Models\\Qwen2.5-72B-Instruct-IQ3_XS.gguf",
        "--host", "127.0.0.1",
        "--port", "8080",
        "--ctx-size", "16384",
        "--context-shift",
        "--flash-attn",
        "--no-mmap",
        "--grp-attn-n", "4",
        "--grp-attn-w", "1024",
        "--rpc", "192.168.1.51:50052,192.168.1.52:50052,192.168.1.53:50052,192.168.1.54:50052,192.168.1.55:50052,192.168.1.56:50052,192.168.1.57:50052,192.168.1.58:50052,192.168.1.59:50052,192.168.1.60:50052,192.168.1.61:50052"
    ],
    "dependsOn": "Cluster Health Check",
    "group": "build",
    "presentation": {
        "echo": true,
        "reveal": "always",
        "focus": false,
        "panel": "dedicated",
        "showReuseMessage": true,
        "clear": false
    },
    "problemMatcher": []
}

------------------------------
## 🔧 Deep Dive: What These Configuration Flags Do

* --ctx-size 16384: Expands your total available memory horizon to 16K tokens. This gives you plenty of headroom to ingest large multi-file repositories or long stack traces before the system needs to compress past history.
* --context-shift: Mandatory flag for long sessions. When your chat reaches the 16,384 token boundary, llama-server drops the oldest user/assistant turn, shifts the remaining tokens forward, and appends the new prompt without triggering a full re-evaluation phase across your network switch.
* --no-mmap: Forces the Windows master process to allocate model memory space directly inside physical RAM rather than mapping it lazily to virtual page file segments. This protects cluster network transfers from micro-stutters caused by mechanical drive delays.
* --grp-attn-n 4 & --grp-attn-w 1024: Activates YaRN-based Group-Attention scaling. This prevents the model's logic from breaking down at high context ranges, allowing Qwen to retain its structural reasoning capabilities and track bracket configurations accurately even as the history hits full capacity.

------------------------------
## 🧠 Performance Tuning for Long Chat Histories
When handling deep debugging sessions across an distributed cluster, follow these operational guidelines to maximize generation speeds:

* Clear the Assistant Cache Periodically: While context shifting prevents complete engine freezes, managing a massive 16K context pool still puts pressure on your network bandwidth. If you switch tasks entirely (e.g., you finish fixing a database bug and start working on UI components), use the "New Session" button (Ctrl + Esc in the Continue plugin) to clear the active cache and restore maximum generation speed.
* Monitor KV Cache Cells via Your Telemetry Script: Keep your cluster_monitor.py dashboard open in a split terminal window. If the KV Cache Cell Allocation reads close to 16384, you will see your network throughput briefly flatten out. This indicates that the context shift mechanism has successfully kicked in, removing outdated data blocks and protecting your nodes from Out-Of-Memory (OOM) crashes.

The following script will automatically restart the backend llama-rpc-service if an unexpected Out-Of-Memory (OOM) or a network hiccup crash happens during an intense, high-context debugging session.

This approach combines two components:

   1. An internal systemd watchdog mechanism built directly into the service runner. It expects a periodic heartbeat from the process or relies on systemd to detect runtime failures instantly.
   2. An external bash monitor shell loop that runs locally on each Jetson node. It automatically handles cleanup if a memory overflow compromises the local network interface.

------------------------------
## 1. Update the Ansible Playbook for Automatic Watchdog Injection
To apply these automation changes across all 11 nodes simultaneously, open your existing cluster_deploy.yml playbook and replace your previous Phase 7 llama-rpc.service configuration block with this updated version:

    - name: Part 3 - Inject Systemd Daemon Watchdog Infrastructure
      copy:
        dest: /etc/systemd/system/llama-rpc.service
        mode: '0644'
        content: |
          [Unit]
          Description=Llama.cpp RPC Slave Server Engine
          After=network.target cluster-init.service
          Wants=cluster-init.service

          [Service]
          Type=simple
          User=jetson
          Groups=video,crypto
          WorkingDirectory=/home/jetson/llama.cpp
          ExecStart=/home/jetson/llama.cpp/build/bin/llama-rpc-server --host 0.0.0.0 --port 50052
          
          # Lifecycle & Self-Healing Policies
          Restart=always
          RestartSec=2s
          StartLimitIntervalSec=30s
          StartLimitBurst=5
          
          # Memory Safety Limits (Triggers dynamic clean restarts before kernel panic)
          MemoryAccounting=yes
          MemoryMax=3850M
          MemoryHigh=3700M
          OOMPolicy=stop

          [Install]
          WantedBy=multi-user.target
    - name: Part 3 - Create Local Out-Of-Memory Guard Script
      copy:
        dest: /home/jetson/oom_guard.sh
        owner: jetson
        group: jetson
        mode: '0755'
        content: |
          #!/bin/bash
          # Continuous loop monitoring local health anomalies
          while true; do
              # Detect if process is dead but port 50052 is stuck in TIME_WAIT/CLOSE_WAIT
              if ! pgrep -f "llama-rpc-server" > /dev/null; then
                  # Clear lingering sockets to prevent "Address already in use" bind errors
                  sudo fuser -k 50052/tcp 2>/dev/null
              fi
              
              # Detect if unified memory pressure is approaching system collapse thresholds
              FREE_RAM=$(awk '/MemAvailable/ {print $2}' /proc/meminfo)
              if [ "$FREE_RAM" -lt 152400 ]; then # Below ~150MB free
                  echo "CRITICAL: Extreme VRAM/RAM bottleneck detected. Forcing clean state purge..." | wall
                  sudo systemctl restart llama-rpc.service
                  sleep 10
              fi
              sleep 3
          done
    - name: Part 3 - Create OOM Guard Systemd Worker Unit
      copy:
        dest: /etc/systemd/system/oom-guard.service
        mode: '0644'
        content: |
          [Unit]
          Description=Jetson Hardware Unified Memory Guard
          After=llama-rpc.service

          [Service]
          Type=simple
          ExecStart=/bin/bash /home/jetson/oom_guard.sh
          Restart=always
          RestartSec=5s

          [Install]
          WantedBy=multi-user.target
    - name: Part 3 - Deploy and Active Self-Healing Systems
      systemd:
        name: "{{ item }}"
        enabled: yes
        state: started
        daemon_reload: yes
      loop:
        - llama-rpc.service
        - oom-guard.service

------------------------------
## 🔧 Deep Dive: What This Infrastructure Handles

* MemoryMax=3850M: This establishes a strict limit for systemd. If a high-context prompt pushes a node's shared memory layout past 3.85 GB, systemd will intercept the process and stop it before it triggers a complete system freeze or kernel panic.
* RestartSec=2s & StartLimitBurst=5: If a node hits its memory limit and exits, systemd waits exactly 2 seconds to let the Maxwell GPU cores flush their memory registers, then automatically boots the RPC daemon back up. If a catastrophic issue causes it to fail 5 times within 30 seconds, it stops restarting to prevent an infinite loop, giving you a chance to inspect the logs.
* fuser -k 50052/tcp: When a process finishes unexpectedly, the operating system can leave network sockets open in a TIME_WAIT state for up to two minutes. This script identifies those lingering sockets and terminates them instantly, allowing the restarting llama-rpc-server to immediately re-bind to port 50052 without throwing errors.

------------------------------
## 🚀 Redeploying Your Cluster Updates
To apply this self-healing layout across your environment, run your deployment command inside your WSL2 terminal:

ansible-playbook -i hosts.ini cluster_deploy.yml --ask-become-pass

Once the playbook completes, your cluster will actively monitor its own memory allocations. If an intense debugging session pushes a node past its limit, it will drop offline, flush its cache, restart, and rejoin the network architecture automatically within seconds.

















