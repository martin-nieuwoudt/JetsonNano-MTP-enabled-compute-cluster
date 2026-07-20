# cluster_deploy.py — Unified Python Orchestrator for 11-Node Jetson Nano Cluster
# Merged from: cluster_deploy.py + launch_cluster.py + monitored_cluster.py
# Runs on Windows 11 host. Modes: init, launch, terminate, poweroff, profile, dashboard

import subprocess
import threading
import time
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- CONFIGURATION (single source of truth) ---
# All changeable facts (node IPs, ports, SSH, daemon memory, binary/dir) live in
# mcp/cluster_config.py. This module imports them — it must never redefine them.
try:
    from mcp.cluster_config import (
        SSH_USER, SSH_OPTS, RPC_PORT, NODE_IPS, NODE_NAMES,
        RPC_BIN_DIR, MLOCK_WRAPPER, RPC_DAEMON_M_NODE0, RPC_DAEMON_M_WORKER,
    )
except Exception:
    SSH_USER = "jetson"
    SSH_OPTS = ["-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null"]
    RPC_PORT = 50052
    NODE_IPS = [f"192.168.50.{i}" for i in range(150, 161)]
    NODE_NAMES = [f"nano{i:02d}" for i in range(11)]
    RPC_BIN_DIR = "/home/jetson/llama.cpp/build/bin"
    MLOCK_WRAPPER = "mlockall_wrapper"
    RPC_DAEMON_M_NODE0 = 3000
    RPC_DAEMON_M_WORKER = 3600

# Resilience / relaunch is owned by cluster_qos (single launch implementation).
try:
    import cluster_qos as qos
except Exception:
    qos = None

JETSON_IPS = NODE_IPS

# Live dashboard globals
node_metrics = {ip: {"total": 0, "free": 0, "status": "Connecting"} for ip in JETSON_IPS}
metrics_lock = threading.Lock()
keep_running = True

# --- SSH HELPERS ---

def run_ssh_cmd(ip, command, timeout=10):
    ssh_cmd = ["ssh"] + SSH_OPTS + [f"{REMOTE_USER}@{ip}", command]
    result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
    return result.returncode, result.stdout, result.stderr

def launch_ssh(ip, command):
    """Start a long-lived remote daemon WITHOUT blocking the caller.

    `ssh -f` authenticates, then forks the SSH client into the background and
    returns immediately. Combined with nohup/setsid + full fd redirection on the
    remote side, the rpc-server keeps running detached from any local session.
    Returns the local subprocess (already backgrounded) or None on failure.
    """
    ssh_cmd = ["ssh", "-f"] + SSH_OPTS + [f"{REMOTE_USER}@{ip}", command]
    try:
        return subprocess.Popen(ssh_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[!] SSH launch failed for {ip}: {e}")
        return None

def ssh_popen(ip, command):
    ssh_cmd = ["ssh"] + SSH_OPTS + [f"{REMOTE_USER}@{ip}", command]
    try:
        return subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except Exception as e:
        print(f"[!] SSH connection failed for {ip}: {e}")
        return None

# --- CORE OPERATIONS ---

def init_node(ip):
    code, out, err = run_ssh_cmd(ip, "sudo nvpmodel -m 0 && sudo jetson_clocks")
    return ip, code, out, err

def launch_rpc_daemon(ip):
    """Launch the rpc-server daemon on one node via the shared QoS launcher.

    Delegates to cluster_qos.relaunch_rpc_daemon so there is exactly ONE launch
    implementation (no divergent copy in this file). Uses the MANDATORY per-node
    -m (Phase 7): node0=3000 (GUI kept), workers=3600 (headless). The mlockall
    wrapper provides memory locking WITHOUT the unsupported --mlock flag.
    """
    if qos is None:
        print(f"[!] cluster_qos unavailable — cannot launch {ip}")
        return ip, 1, "", "cluster_qos import failed"
    m = RPC_DAEMON_M_NODE0 if ip == JETSON_IPS[0] else RPC_DAEMON_M_WORKER
    ok = qos.relaunch_rpc_daemon(ip, port=RPC_PORT, m=m)
    return ip, (0 if ok else 1), "", ""

def terminate_rpc_daemon(ip):
    print(f"[*] {ip}: Terminating RPC daemon...")
    # Bracket trick [r]pc-server prevents pkill from matching its own ssh
    # command string (which contains "rpc-server"), avoiding a self-kill hang.
    # Binary at the pinned commit b56f079e2 is 'rpc-server' (not 'llama-rpc-server').
    code, out, err = run_ssh_cmd(ip, "pkill -9 -f '[r]pc-server' || true")
    return ip, code, out, err

def power_off_node(ip):
    code, out, err = run_ssh_cmd(ip, "sudo shutdown -h now", timeout=5)
    return ip, code, out, err

def profile_node(ip):
    code, out, err = run_ssh_cmd(ip, "tegrastats --interval 1000 | head -n 3")
    return ip, code, out, err

def get_rpc_string():
    return ",".join(f"{ip}:{RPC_PORT}" for ip in JETSON_IPS)

# --- LIVE MEMORY DASHBOARD ---

def track_node_memory(ip):
    mem_cmd = "awk '/MemTotal|MemAvailable/ {print $2}' /proc/meminfo"
    while keep_running:
        try:
            code, out, _ = run_ssh_cmd(ip, mem_cmd, timeout=5)
            if code == 0 and out.strip():
                lines = out.strip().split('\n')
                if len(lines) >= 2:
                    total_mb = int(lines[0]) // 1024
                    avail_mb = int(lines[1]) // 1024
                    used_mb = total_mb - avail_mb
                    with metrics_lock:
                        node_metrics[ip] = {"total": total_mb, "free": avail_mb, "used": used_mb, "status": "Online"}
            else:
                with metrics_lock:
                    node_metrics[ip]["status"] = "SSH Error"
        except subprocess.TimeoutExpired:
            with metrics_lock:
                node_metrics[ip]["status"] = "Timeout"
        except Exception:
            with metrics_lock:
                node_metrics[ip]["status"] = "Offline"
        time.sleep(3)

def display_dashboard():
    while keep_running:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("=" * 85)
        print(" JETSON 11-NODE CLUSTER ORCHESTRATOR & MEMORY MONITOR ")
        print("=" * 85)
        print(f"{'Node IP':<16} | {'Status':<10} | {'Used Memory':<13} | {'RAM avail (UMA)':<16} | {'Bar Graph'}")
        print("-" * 85)
        total_free = 0
        total_mem = 0
        with metrics_lock:
            for ip, stats in node_metrics.items():
                status = stats.get("status", "Unknown")
                if status == "Online":
                    used, free, total = stats["used"], stats["free"], stats["total"]
                    total_free += free
                    total_mem += total
                    pct = used / total if total > 0 else 0
                    bars = int(pct * 20)
                    graph = f"[{'#' * bars}{'-' * (20 - bars)}]"
                    print(f"{ip:<16} | \033[92m{status:<10}\033[0m | {used:>4} MB / {total} MB | {free:>5} MB Free      | {graph}")
                else:
                    print(f"{ip:<16} | \033[91m{status:<10}\033[0m | ---- / ---- MB | --------- MB Free | [--------------------]")
        print("-" * 85)
        if total_mem > 0:
            pooled_used = total_mem - total_free
            print(f"POOLED CLUSTER: Used: {pooled_used/1024:.2f} GB / Total: {total_mem/1024:.2f} GB | Free RAM Pool (UMA): {total_free/1024:.2f} GB")
        print("=" * 85)
        print("\n[Instructions] Run your llama-cli command in a separate window.")
        print("Press Ctrl+C here to safely shut down the entire backend array.")
        time.sleep(2)

# --- BATCH MODE ---

def run_batch(action):
    actions = {
        "init": init_node, "launch": launch_rpc_daemon,
        "terminate": terminate_rpc_daemon, "poweroff": power_off_node, "profile": profile_node,
    }
    func = actions.get(action)
    if not func:
        print(f"Unknown action: {action}. Use: init | launch | terminate | poweroff | profile | dashboard | watchdog")
        sys.exit(1)
    with ThreadPoolExecutor(max_workers=11) as executor:
        futures = [executor.submit(func, ip) for ip in JETSON_IPS]
        for future in as_completed(futures):
            ip, code, out, _ = future.result()
            print(f"[{ip}] Exit: {code} | {out.strip()[:80]}")

# --- DASHBOARD MODE (default) ---

def run_dashboard():
    global keep_running
    server_procs = []
    threads = []
    print("[*] Contacting 11 nodes and spinning up RPC servers...")
    for ip in JETSON_IPS:
        # Use the SAME safe launch as launch_rpc_daemon: via mlockall_wrapper
        # (correct binary name, correct flags, memory cap + mlock via wrapper).
        # Per-node -m: node0=3000 (GUI kept), workers=3600 (headless).
        m = RPC_DAEMON_M_NODE0 if ip == JETSON_IPS[0] else RPC_DAEMON_M_WORKER
        launch_cmd = (
            f"cd {RPC_BIN_DIR} && nohup ./{MLOCK_WRAPPER} "
            f"-H 0.0.0.0 -p {RPC_PORT} -m {m} "
            f"< /dev/null > /home/{SSH_USER}/llama_rpc.log 2>&1 &"
        )
        proc = ssh_popen(ip, launch_cmd)
        if proc:
            server_procs.append(proc)
        t = threading.Thread(target=track_node_memory, args=(ip,), daemon=True)
        threads.append(t)
        t.start()
    time.sleep(2)
    rpc_targets = get_rpc_string()
    print("\n" + "=" * 90)
    print(" TARGET EXECUTION STRING (run in a second terminal)")
    print("=" * 90)
    print(f'llama-cli.exe -m C:\\Models\\Qwen2.5-72B-Instruct-IQ3_XS.gguf --flash-attn --rpc {rpc_targets} -p "Your prompt here"')
    print("=" * 90)
    input("\nPress ENTER to open live memory dashboard...")
    dash_thread = threading.Thread(target=display_dashboard, daemon=True)
    dash_thread.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[!] Shutting down cluster...")
        keep_running = False
        for proc in server_procs:
            proc.kill()
        print("[✓] Clean exit achieved.")
        sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] == "dashboard":
        run_dashboard()
    elif sys.argv[1] == "watchdog":
        # Fault-tolerant RPC watchdog: re-slices the live node set on node-drop
        # or thermal WARN so the Windows host survives the data barrage.
        import cluster_watchdog
        cluster_watchdog.main()
    else:
        run_batch(sys.argv[1])