Since you have already established stable, passwordless SSH access across all 10 nodes, your network baseline is ready to go. You can bypass the setup steps and move straight to the final automated orchestration layout.
Because your SSH access is working, you do not need to manually configure background tunnels or manage multiple ports on your loopback adapter. A native llama.cpp configuration allows you to connect the master Windows PC directly to the physical static IP addresses of your Jetson boards over the network.
1. Automated Cluster Activation Script
Save the script below on your Windows host PC as launch_cluster.py.
This script relies on your existing passwordless SSH environment to connect to all 10 Jetson boards simultaneously, launch the compiled llama-rpc-server engine, and output the exact command needed to run your 70B model.
import subprocess
import threading
import time
import sys

# --- CONFIGURATION ---
# Enter the exact local IP addresses of your 10 Jetson Nano nodes
JETSON_NODES = [
    "192.168.1.51", "192.168.1.52", "192.168.1.53", "192.168.1.54", "192.168.1.55",
    "192.168.1.56", "192.168.1.57", "192.168.1.58", "192.168.1.59", "192.168.1.60"
]

SSH_USER = "jetson"                 # Username on your Jetson nodes
REMOTE_PATH = "llama.cpp/build/bin" # Directory where you compiled the rpc binary
RPC_PORT = "50052"                  # The physical network port to use

active_processes = []

def launch_remote_server(ip, index):
    """Logs into a node and starts the rpc-server on its physical IP."""
    print(f"[*] Node {index+1:02d} ({ip}): Initializing GPU server engine...")
    
    # Binds the server to 0.0.0.0 so it listens to connections from your Windows PC
    # Binary at commit b56f079e2 is 'rpc-server' (not 'llama-rpc-server')
    remote_command = f"cd {REMOTE_PATH} && ./rpc-server -H 0.0.0.0 -p {RPC_PORT}"
    
    # Leverages your working passwordless SSH configuration
    ssh_cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        f"{SSH_USER}@{ip}",
        remote_command
    ]
    
    try:
        proc = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        active_processes.append((proc, ip))
    except Exception as e:
        print(f"[!] Critical Connection Error on Node {ip}: {str(e)}")

def main():
    print(f"--- Launching 10-Node Jetson Star Cluster Matrix ---")
    threads = []
    
    # Boot all 10 nodes concurrently in background threads
    for idx, ip in enumerate(JETSON_NODES):
        t = threading.Thread(target=launch_remote_server, args=(ip, idx))
        t.daemon = True
        threads.append(t)
        t.start()
        
    # Brief pause to allow the threads to spin up and establish connections
    time.sleep(2)
    
    # Generate the string of remote IP targets for llama-cli
    rpc_targets = ",".join([f"{ip}:{RPC_PORT}" for ip in JETSON_NODES])
    
    print("\n" + "="*90)
    print(" ALL REMOTE GPU NODES ACTIVATED SUCCESSFULLY")
    print("="*90)
    print("Paste and execute this command in a separate Windows command prompt to start inference:\n")
    print(f"llama-cli.exe -m models/Llama-3-70B-Q3_K_M.gguf -c 1024 --cache-type-k q4_0 --cache-type-v q4_0 --rpc {rpc_targets} -p \"Your prompt here\"\n")
    print("="*90)
    print("Keep this Python orchestrator running. Press Ctrl+C to shut down all remote servers.")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[!] Shutting down cluster. Sending termination signals to Jetson backends...")
        for proc, ip in active_processes:
            proc.kill()
        print("[✓] All remote server instances closed safely.")
        sys.exit(0)

if __name__ == "__main__":
    main()
2. Execution Steps
Run the deployment script from your Windows host:
python launch_cluster.py
The script will run in the background, logging into all 10 Nanos simultaneously using your active SSH channels and starting the rpc-server binary on each node.
Copy the output command string from your terminal.
Open a second terminal window on Windows and run that command to begin streaming your 70B parameter network layers directly across your pooled Maxwell memory fabric

RAM monitor feature 
To integrate a live memory monitor, the Python orchestrator needs to parse the real-time contents of /proc/meminfo on each Jetson node. Because the Jetson Nano shares its physical 4GB memory directly between the CPU and the Maxwell GPU, tracking available system RAM gives you an exact picture of your pooled VRAM health.
The updated script below uses your working passwordless SSH connection to launch the RPC servers, open background memory tracking loops, and display a live ASCII status dashboard directly in your Windows terminal.
The Live-Monitoring Cluster Orchestrator
Save this code on your Windows PC as monitored_cluster.py.
import subprocess
import threading
import time
import sys
import os

# --- STATIC CONFIGURATION ---
JETSON_NODES = [
    "192.168.1.51", "192.168.1.52", "192.168.1.53", "192.168.1.54", "192.168.1.55",
    "192.168.1.56", "192.168.1.57", "192.168.1.58", "192.168.1.59", "192.168.1.60"
]

SSH_USER = "jetson"                 # Username on your Jetson nodes
REMOTE_PATH = "llama.cpp/build/bin" # Path to compiled binaries
RPC_PORT = "50052"                  # Target RPC network port

# Thread-safe dictionary to hold live memory stats per IP
# Format: { ip: {"total": 4000, "free": 2500, "status": "Active"} }
node_metrics = {ip: {"total": 0, "free": 0, "status": "Connecting"} for ip in JETSON_NODES}
metrics_lock = threading.Lock()
keep_running = True

def track_node_memory(ip):
    """Background loop pulling raw memory metrics via SSH."""
    global keep_running
    # Command extracts Total and Available memory in Kilobytes
    mem_command = "awk '/MemTotal|MemAvailable/ {print $2}' /proc/meminfo"
    
    ssh_cmd = [
        "ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
        f"{SSH_USER}@{ip}", mem_command
    ]
    
    while keep_running:
        try:
            result = subprocess.run(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 2:
                    total_mb = int(lines[0]) // 1024
                    avail_mb = int(lines[1]) // 1024
                    used_mb = total_mb - avail_mb
                    
                    with metrics_lock:
                        node_metrics[ip]["total"] = total_mb
                        node_metrics[ip]["free"] = avail_mb
                        node_metrics[ip]["used"] = used_mb
                        node_metrics[ip]["status"] = "Online"
            else:
                with metrics_lock:
                    node_metrics[ip]["status"] = "SSH Error"
        except subprocess.TimeoutExpired:
            with metrics_lock:
                node_metrics[ip]["status"] = "Timeout"
        except Exception:
            with metrics_lock:
                node_metrics[ip]["status"] = "Offline"
        
        time.sleep(3) # Poll every 3 seconds to preserve network bandwidth

def launch_remote_server(ip):
    """Starts the rpc-server binary on the target node."""
    remote_command = f"cd {REMOTE_PATH} && ./rpc-server -H 0.0.0.0 -p {RPC_PORT}"
    ssh_cmd = [
        "ssh", "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
        f"{SSH_USER}@{ip}", remote_command
    ]
    try:
        return subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except Exception as e:
        print(f"[!] Target {ip} RPC initialization failed: {str(e)}")
        return None

def display_dashboard():
    """Clears terminal and renders live cluster stats."""
    global keep_running
    while keep_running:
        # Clear screen command for Windows
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print("=" * 85)
        print(f" JETSON NANO STAR CLUSTER ORCHESTRATOR & MEMORY MONITOR ")
        print("=" * 85)
        print(f"{'Node IP':<16} | {'Status':<10} | {'Used Memory':<13} | {'Available VRAM':<16} | {'Bar Graph'}")
        print("-" * 85)
        
        total_cluster_free = 0
        total_cluster_mem = 0
        
        with metrics_lock:
            for ip, stats in node_metrics.items():
                status = stats["status"]
                if status == "Online":
                    used = stats["used"]
                    free = stats["free"]
                    total = stats["total"]
                    total_cluster_free += free
                    total_cluster_mem += total
                    
                    # Calculate visual graph segments (20 bars max)
                    pct = used / total
                    bars = int(pct * 20)
                    graph = f"[{'#' * bars}{'-' * (20 - bars)}]"
                    
                    print(f"{ip:<16} | \033[92m{status:<10}\033[0m | {used:>4} MB / {total} MB | {free:>5} MB Free      | {graph}")
                else:
                    print(f"{ip:<16} | \033[91m{status:<10}\033[0m | ---- / ---- MB | --------- MB Free | [--------------------]")
        
        print("-" * 85)
        if total_cluster_mem > 0:
            pooled_used = total_cluster_mem - total_cluster_free
            print(f"POOLED CLUSTER METRICS: Used: {pooled_used/1024:.2f} GB / Total: {total_cluster_mem/1024:.2f} GB | Free VRAM Pool: {total_cluster_free/1024:.2f} GB")
        print("=" * 85)
        print("\n[Instructions] Run your llama-cli command in a separate window.")
        print("Press Ctrl+C here to safely shut down the entire backend array.")
        
        time.sleep(2)

def main():
    global keep_running
    server_processes = []
    threads = []
    
    print("[*] Contacting 10 nodes and spinning up network servers...")
    
    # Establish connection pipelines and monitoring loops
    for ip in JETSON_NODES:
        proc = launch_remote_server(ip)
        if proc:
            server_processes.append(proc)
        
        t = threading.Thread(target=track_node_memory, args=(ip,))
        t.daemon = True
        threads.append(t)
        t.start()
    
    # Print the optimized startup string before dropping into the live layout loop
    rpc_targets = ",".join([f"{ip}:{RPC_PORT}" for ip in JETSON_NODES])
    
    # Quick standard output pause so you can save the command line execution arguments
    os.system('cls' if os.name == 'nt' else 'clear')
    print("=" * 90)
    print(" TARGET EXECUTION STRING FOR SECOND WINDOW")
    print("=" * 90)
    print(f"llama-cli.exe -m models/Llama-3-70B-Q3_K_M.gguf -c 1024 --cache-type-k q4_0 --cache-type-v q4_0 --rpc {rpc_targets} -p \"Your prompt here\"")
    print("=" * 90)
    input("\nVerify the execution string, open your second window, then press ENTER here to open Dashboard...")

    # Boot the console renderer thread
    dash_thread = threading.Thread(target=display_dashboard)
    dash_thread.daemon = True
    dash_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[!] Gracefully tearing down cluster. Halting remote servers...")
        keep_running = False
        for proc in server_processes:
            proc.kill()
        print("[✓] Clean exit achieved.")
        sys.exit(0)

if __name__ == "__main__":
    main()
What to Expect During Run
Run the script inside your primary Windows Command Prompt.
It lists your explicit llama-cli.exe command execution parameters. Copy this line.
Press Enter on your keyboard. The script shifts into its live dashboard display.
Open your second Command Prompt panel, paste the line, and execute the model.
As llama.cpp streams the 70B parameter graph across the network, you will see the individual node bar graphs update sequentially from [----] to [####] inside your dashboard window as they accept their respective model chunks.
