#!/usr/bin/env python3
"""
cluster_qos.py — Integrity & resilience layer for the Jetson Nano RPC cluster
============================================================================
Single source of truth for cluster QoS configuration AND the three cheap
integrity/resilience checks that wrap inference. Imported by cluster_infer.py
so the checks run automatically before/around every inference.

WHY THIS EXISTS
---------------
The inter-node inference payloads move over llama.cpp's RPC protocol (port
50052). That transport relies on TCP (per-packet checksum only) + llama.cpp's
RPC framing. There is NO application-level integrity, lost-chunk recovery, or
resilience. On a slow cluster with many ethernet transitions, a dropped RPC
daemon or a corrupted GGUF on one worker silently degrades or fails a run.

This module adds three CHEAP guards that do NOT measurably hurt time-to-answer:

  #1 preflight_model_hash  — sha256 the GGUF on EVERY node in parallel before
                             launch; abort if any mismatch (bad flash / SSD
                             bit-rot). One disk-speed pass per launch, seconds
                             to minutes, vs. an inference that runs much longer.

  #3 golden_prompt_check   — run ONE fixed calibration prompt and compare the
                             output hash to a known-good value (bootstrapped on
                             first run). Catches weight/model corruption that
                             changes results. One small extra inference (~secs).
                             NOTE: this is NOT per-node output comparison — RPC
                             is collective, so there is no per-node answer to
                             hash. It is a whole-cluster determinism assertion.

  #4 run_with_retry        — resilience wrapper. If an RPC daemon drops mid-run
                             (port closes / non-zero exit), relaunch it on the
                             affected node(s) and re-issue the prompt. NO
                             bandwidth throttling (that WOULD hurt time-to-answer
                             on an already-slow cluster).

CONFIG (authoritative — change here only; cluster_infer.py imports from here):
"""

import hashlib
import json
import os
import subprocess
import sys
import time

import paramiko

HERE = os.path.dirname(os.path.abspath(__file__))

# --- AUTHORITATIVE CONFIG --------------------------------------------------
# Single source of truth is mcp/cluster_config.py. Import it when available so
# node IPs / ports / model paths / daemon buffers are defined in EXACTLY ONE
# place (satisfies the work-plan "changeable logic is never hardcoded" invariant).
# Fall back to local copies only if the MCP package is not importable.
try:
    import mcp.cluster_config as cfg
    RPC_PORT = cfg.RPC_PORT
    SSH_USER = cfg.SSH_USER
    SSH_KEY_PATH = cfg.SSH_KEY_PATH
    NODE_IPS = cfg.NODE_IPS
    MODEL_NODE_IP = cfg.MODEL_NODE_IP
    MODEL_DIR_ON_NODE0 = cfg.MODEL_DIR_ON_NODE0
    MODEL_MOUNT_ON_WORKER = cfg.MODEL_MOUNT_ON_WORKER
    RPC_DAEMON_M_NODE0 = cfg.RPC_DAEMON_M_NODE0
    RPC_DAEMON_M_WORKER = cfg.RPC_DAEMON_M_WORKER
    RPC_BIN_DIR = cfg.RPC_BIN_DIR
    MLOCK_WRAPPER = cfg.MLOCK_WRAPPER
    GOLDEN_PROMPT = cfg.GOLDEN_PROMPT
    GOLDEN_TOKENS = cfg.GOLDEN_TOKENS
except Exception:
    RPC_PORT = 50052
    SSH_USER = "jetson"
    SSH_KEY_PATH = r"C:\Users\marti\.ssh\id_ed25519"
    NODE_IPS = [f"192.168.50.{i}" for i in range(150, 161)]  # nano00..nano10
    MODEL_NODE_IP = "192.168.50.150"          # Nano Zero = the model store
    MODEL_DIR_ON_NODE0 = "/mnt/ssd/models"    # node0 local SSD path
    MODEL_MOUNT_ON_WORKER = "/mnt/nano-ssd"   # NFS mount point on workers
    RPC_DAEMON_M_NODE0 = 3000
    RPC_DAEMON_M_WORKER = 3600
    GOLDEN_PROMPT = "The chemical symbol for water is"
    GOLDEN_TOKENS = 24

# Model storage architecture (RETIRED 2026-07-15 — see cluster_config.py):
#   - The node0 USB SSD was REMOVED and reformatted as a local PC drive (D:).
#   - ALL GGUFs now live on the PC at C:\Models (MODELS_DIR); the PC pushes every
#     shard over RPC on each run. Nodes NEVER load from disk.
#   - There is NO on-node model store and NO NFS mount anymore.
# The authoritative GGUF copy is now on the PC; hash it THERE (not on node0).
# NOTE: preflight_model_hash() below still ssh's to MODEL_NODE_IP to sha256sum —
# that path is retired and will fail; repoint it to hash the PC-side file.

KNOWN_GOOD_HASH_FILE = os.path.join(HERE, "golden_prompt.sha256")

# RPC daemon relaunch command (mirrors cluster_deploy.py launch_rpc_daemon).
# Uses the setuid mlockall_wrapper so memory locking works at pinned commit.
# Includes the MANDATORY per-node -m (Phase 7): node0=3000, workers=3600.
# NOTE: mlockall_wrapper execv's ./rpc-server itself (binary name at b56f079e2),
# so we must NOT pass ./rpc-server as an extra argument here — that would become
# a stray positional arg to rpc-server. The wrapper's argv is the rpc-server flags.
RELAUNCH_CMD = (
    "nohup setsid bash -c 'cd {bin_dir} && "
    "exec ./{wrapper} -H 0.0.0.0 -p {port} -m {m} "
    ">> /home/jetson/rpc-server.log 2>&1' < /dev/null &"
)

SSH_OPTS = {"StrictHostKeyChecking": "no", "UserKnownHostsFile": "/dev/null"}


class QosError(Exception):
    """Raised when a QoS guard fails and the run must not proceed."""


# --- LOW-LEVEL SSH ----------------------------------------------------------
def ssh_exec(ip, cmd, timeout=10):
    """Run a command on a node via paramiko. Returns (rc, stdout, stderr)."""
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(ip, username=SSH_USER, key_filename=SSH_KEY_PATH,
                    timeout=timeout, compress=True)
        _, o, e = ssh.exec_command(cmd, timeout=timeout)
        out = o.read().decode("utf-8", "replace")
        err = e.read().decode("utf-8", "replace")
        rc = o.channel.recv_exit_status()
        return rc, out, err
    except Exception as ex:
        return -1, "", str(ex)
    finally:
        try:
            ssh.close()
        except Exception:
            pass


def check_rpc_ports(ips=None):
    """TCP connect probe for the RPC daemon on each node. Returns {ip: bool}."""
    import socket
    ips = ips or NODE_IPS
    out = {}
    for ip in ips:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2.0)
                out[ip] = s.connect_ex((ip, RPC_PORT)) == 0
        except Exception:
            out[ip] = False
    return out


# --- #1 PRE-FLIGHT MODEL HASH ----------------------------------------------
def preflight_model_hash(model_path):
    """sha256 the GGUF on the PC (the authoritative model store).

    All orchestration is PC-side: the GGUF lives on the PC (e.g. C:\\Models) and
    the PC pushes every shard over RPC to the Nano nodes on each run. There is
    NO on-node model store and NO NFS mount (the node0 SSD was removed and
    reformatted as a local PC drive on 2026-07-15). So we hash the single
    authoritative copy on the PC and compare it to the known-good sidecar.
    `model_path` is the PC-side GGUF path (e.g. C:\Models\X.gguf). Returns
    {"pc": hash}.

    Raises QosError if the file is missing or the hash disagrees with the
    known-good sidecar (if a sidecar exists).
    """
    ip = "pc"
    print(f"[QOS#1] pre-flight sha256 of {model_path} on PC model store ...",
          file=sys.stderr)

    if not os.path.exists(model_path):
        raise QosError(f"PRE-FLIGHT MODEL HASH FAILED: file not found at "
                       f"{model_path}")
    h = _sha256_file(model_path)
    if not h or len(h) != 64:
        raise QosError(f"PRE-FLIGHT MODEL HASH FAILED: no valid hash for "
                       f"{model_path}")

    # Compare against the known-good sidecar if present. The sidecar sits next to
    # the GGUF itself: <model_path>.sha256 (e.g.
    # C:\Models\Codestral-22B-v0.1-Q8_0.gguf.sha256).
    pc_sidecar = model_path + ".sha256"
    if os.path.exists(pc_sidecar):
        with open(pc_sidecar, "r", encoding="utf-8") as fh:
            exp = fh.read().strip().split()[0].lower()
        if h != exp:
            raise QosError(f"PRE-FLIGHT MODEL HASH MISMATCH: "
                           f"got {h}, expected {exp}")
        print(f"[QOS#1] OK — matches PC known-good {h}", file=sys.stderr)
    else:
        print(f"[QOS#1] OK — PC hash {h} (no sidecar to compare)",
              file=sys.stderr)
    return {ip: h}


def _sha256_file(path, chunk=1 << 20):
    """Streaming sha256 of a local file (memory-safe for multi-GB GGUFs)."""
    import hashlib
    m = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(chunk), b""):
            m.update(block)
    return m.hexdigest()


# --- #3 GOLDEN-PROMPT DETERMINISM CHECK ------------------------------------
def _hash_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def golden_prompt_check(model, nodes="all", model_on_node=None,
                         bootstrap=False, infer_script=None):
    """Run the fixed golden prompt through cluster_infer.py and check output hash.

    bootstrap=True  -> store the observed hash as known-good (first validated run).
    bootstrap=False -> compare against stored known-good hash; return (ok, got, exp).
    """
    infer_script = infer_script or os.path.join(HERE, "cluster_infer.py")
    # The PC llama-cli.exe -m loads the GGUF from the PC filesystem, NOT the
    # node's. So we pass the PC path `model` (e.g. C:\Models\...gguf). The nodes
    # reach the SAME weights via their NFS mount of node0's SSD at /mnt/nano-ssd;
    # the client path and the node path are different views of the same file.
    model_on_node = model_on_node or model

    cmd = [sys.executable, infer_script,
           "--prompt", GOLDEN_PROMPT,
           "--model", model_on_node,
           "--nodes", nodes,
           "--tokens", str(GOLDEN_TOKENS),
           "--json"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=600)
    except Exception as ex:
        return False, "", f"infer subprocess error: {ex}"

    try:
        data = json.loads(res.stdout)
    except Exception:
        return False, "", f"no JSON from infer: {res.stdout[:120]} {res.stderr[:120]}"

    gen = data.get("generation", "")
    got = _hash_text(gen)

    if bootstrap or not os.path.exists(KNOWN_GOOD_HASH_FILE):
        with open(KNOWN_GOOD_HASH_FILE, "w", encoding="utf-8") as fh:
            fh.write(got + "\n")
        print(f"[QOS#3] bootstrapped known-good hash: {got}", file=sys.stderr)
        return True, got, got

    with open(KNOWN_GOOD_HASH_FILE, "r", encoding="utf-8") as fh:
        exp = fh.read().strip().split()[0]
    ok = (got == exp)
    print(f"[QOS#3] {'OK' if ok else 'MISMATCH'} got={got} expected={exp}",
          file=sys.stderr)
    return ok, got, exp


# --- #4 RETRY / HEALTH WRAPPER ---------------------------------------------
def relaunch_rpc_daemon(ip, port=RPC_PORT, launch_cmd=None, m=None):
    """Relaunch the rpc-server daemon on a single node. Returns True on success.

    m = backend memory buffer (-m). MANDATORY per Phase 7: node0=3000 (GUI kept),
    workers=3600 (headless). Defaults to the worker value.
    """
    m = m or RPC_DAEMON_M_WORKER
    cmd = (launch_cmd or RELAUNCH_CMD).format(
        port=port, m=m, bin_dir=RPC_BIN_DIR, wrapper=MLOCK_WRAPPER)
    rc, _, err = ssh_exec(ip, cmd, timeout=15)
    if rc != 0:
        print(f"[QOS#4] relaunch FAILED on {ip}: {err.strip()}", file=sys.stderr)
        return False
    # Give the daemon a moment to bind the port.
    for _ in range(10):
        if check_rpc_ports([ip]).get(ip):
            print(f"[QOS#4] rpc-server relaunched on {ip}", file=sys.stderr)
            return True
        time.sleep(1.0)
    print(f"[QOS#4] relaunch on {ip} did not open port {port}", file=sys.stderr)
    return False


def run_with_retry(exec_fn, ips=None, max_retries=2, port=RPC_PORT):
    """Wrap an inference execution with resilience.

    exec_fn() runs the inference and returns a result dict with key 'ok'
    (bool) and 'returncode'. On failure, any node whose RPC port is now down
    gets its daemon relaunched, then the prompt is re-issued (up to
    max_retries). NO throttling — throughput is untouched.
    """
    ips = ips or NODE_IPS
    for attempt in range(max_retries + 1):
        result = exec_fn()
        ok = bool(result.get("ok")) if isinstance(result, dict) else (result == 0)
        if ok:
            return result
        if attempt == max_retries:
            return result
        print(f"[QOS#4] attempt {attempt + 1} failed; checking node health ...",
              file=sys.stderr)
        ports = check_rpc_ports(ips)
        down = [ip for ip, up in ports.items() if not up]
        if not down:
            print("[QOS#4] no down nodes detected; not retrying blindly",
                  file=sys.stderr)
            return result
        print(f"[QOS#4] relaunching rpc-server on {len(down)} down node(s): "
              f"{down}", file=sys.stderr)
        for ip in down:
            relaunch_rpc_daemon(ip, port=port)
    return result
