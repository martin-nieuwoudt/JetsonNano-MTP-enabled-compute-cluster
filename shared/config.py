"""
Shared configuration constants for the Jetson Nano MTP-enabled compute cluster.

Topology: star — one Windows Master PC (hub) coordinating 11 Jetson Nano workers
          (leaves) over a 1 Gbps Ethernet network.
"""

# ---------------------------------------------------------------------------
# Cluster topology
# ---------------------------------------------------------------------------
CLUSTER_NODE_COUNT = 11          # Number of Jetson Nano worker nodes
NETWORK_BANDWIDTH_GBPS = 1       # Inter-node bandwidth

# ---------------------------------------------------------------------------
# Master coordinator
# ---------------------------------------------------------------------------
MASTER_HOST = "0.0.0.0"          # Bind address for the master coordinator
MASTER_PORT = 7000               # TCP port the master listens on for worker registration
MASTER_API_PORT = 7001           # REST/HTTP port for external task submission

# ---------------------------------------------------------------------------
# Worker (Jetson Nano) services
# ---------------------------------------------------------------------------
WORKER_PORT = 7010               # TCP port each worker listens on for task dispatch
WORKER_HEARTBEAT_INTERVAL = 5    # Seconds between worker → master heartbeats
WORKER_HEARTBEAT_TIMEOUT = 15    # Seconds without heartbeat before node is marked offline

# ---------------------------------------------------------------------------
# Worker (Jetson Nano) task listener
# ---------------------------------------------------------------------------
# Bind address for the worker's task-dispatch listener.  In a dedicated
# cluster VLAN, binding to all interfaces is intentional so that the master
# can reach the worker regardless of which NIC the traffic arrives on.
WORKER_LISTEN_HOST = "0.0.0.0"

# ---------------------------------------------------------------------------
# llama.cpp RPC server (runs on each Jetson Nano)
# ---------------------------------------------------------------------------
LLAMACPP_RPC_PORT = 50052        # Default RPC server port (can be overridden per node)
# Bind address for the llama-rpc-server on each Nano.  All interfaces are
# needed so the master can connect over the cluster VLAN.
LLAMACPP_RPC_HOST = "0.0.0.0"
LLAMACPP_BINARY = "llama-rpc-server"  # Name of the llama.cpp RPC server binary
# Number of model layers offloaded to the GPU via RPC (99 = all layers).
# Set to a smaller value to split layers between CPU and GPU.
N_GPU_LAYERS_ALL = 99

# ---------------------------------------------------------------------------
# PyCUDA workload dispatch
# ---------------------------------------------------------------------------
PYCUDA_TASK_PORT = 7020          # TCP port used for PyCUDA task submissions

# ---------------------------------------------------------------------------
# Network / timeouts
# ---------------------------------------------------------------------------
SOCKET_TIMEOUT = 30              # Seconds for individual socket operations
TASK_TIMEOUT = 300               # Seconds before a dispatched task is considered failed
