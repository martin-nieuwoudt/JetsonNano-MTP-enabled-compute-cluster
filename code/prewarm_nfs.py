#!/usr/bin/env python3
"""
prewarm_nfs.py — SSD weight prewarm for the Jetson Nano RPC cluster
==================================================================
Single source of truth for forcing each worker's OS page cache to hold the
model weight shard BEFORE inference, so the RPC weight-upload step reads from
RAM (page cache) instead of hitting node0's SSD over NFS.

WHY THIS EXISTS
---------------
Per the cluster architecture (Phase 9e / Prewarm script for SSD models.md):
  - ALL GGUFs live on Nano Zero's USB SSD and are NFS-exported to workers.
  - Workers mount it read-only at MODEL_MOUNT_ON_WORKER (/mnt/nano-ssd).
  - The llama.cpp RPC client pushes each node's weight shard over the 1 Gbps
    switch on every inference run (~200 s penalty for a 25 GB model).

The prewarm reads the GGUF straight from the worker's local NFS mount and
touches every page (dd if=<gguf> of=/dev/null). After prewarm, subsequent NFS
reads hit the OS page cache in RAM, so the RPC upload reads from memory instead
of the SSD. This is the "quick win" from the work plan: zero binary changes,
deployable to all workers via SSH.

The prewarm is idempotent: if the model is already cached, dd still runs but
returns almost instantly from cache. It is also best-effort: a worker that is
down or whose mount is missing is reported but does NOT abort the run (the RPC
layer still works, just without the cache speed-up).

CONFIG (authoritative — change here only; cluster_infer.py imports from here):
"""

import os
import sys
import time

import paramiko

HERE = os.path.dirname(os.path.abspath(__file__))

# --- AUTHORITATIVE CONFIG --------------------------------------------------
# Single source of truth is mcp/cluster_config.py. Import it when available so
# node IPs / ports / model paths / mount points are defined in EXACTLY ONE
# place (satisfies the work-plan "changeable logic is never hardcoded" invariant).
try:
    import mcp.cluster_config as cfg
    SSH_USER = cfg.SSH_USER
    SSH_KEY_PATH = cfg.SSH_KEY_PATH
    NODE_IPS = cfg.NODE_IPS
    MODEL_NODE_IP = cfg.MODEL_NODE_IP
    MODEL_DIR_ON_NODE0 = cfg.MODEL_DIR_ON_NODE0
    MODEL_MOUNT_ON_WORKER = cfg.MODEL_MOUNT_ON_WORKER
    RPC_PORT = cfg.RPC_PORT
except Exception:
    SSH_USER = "jetson"
    SSH_KEY_PATH = r"C:\Users\marti\.ssh\id_ed25519"
    NODE_IPS = [f"192.168.50.{i}" for i in range(150, 161)]  # nano00..nano10
    MODEL_NODE_IP = "192.168.50.150"          # Nano Zero = the model store
    MODEL_DIR_ON_NODE0 = "/mnt/ssd/models"    # node0 local SSD path
    MODEL_MOUNT_ON_WORKER = "/mnt/nano-ssd"   # NFS mount point on workers
    RPC_PORT = 50052

# NFS mount options used when the worker mount is missing. vers=3 + nolock is
# the proven combo for the Jetson NFS client against node0's export.
NFS_MOUNT_OPTS = "nolock,vers=3,ro"
# dd block size for the page-cache sweep. 4M is a good balance of throughput
# and readahead on the Jetson.
PREWARM_BS = "4M"
# Per-worker prewarm timeout (seconds). A 25 GB model over 1 Gbps NFS is ~30 s;
# allow generous headroom for cold cache + slow SD-backed NFS.
PREWARM_TIMEOUT = 300


def _ssh_exec(ip, cmd, timeout=30):
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


def _ensure_nfs_mount(ip):
    """Make sure the worker has the model SSD NFS-mounted. Returns True if the
    mount is present (or was successfully mounted) afterwards."""
    # POSIX join so we never inject a Windows backslash into the remote path.
    remote = "{0}:/{1}".format(MODEL_NODE_IP, MODEL_DIR_ON_NODE0.strip("/"))
    mountpoint = MODEL_MOUNT_ON_WORKER
    check = (
        "mount | grep -q '{mp}' && echo MOUNTED || "
        "(sudo mkdir -p {mp} && "
        "sudo mount -t nfs -o {opts} {remote} {mp} && echo MOUNTED_NOW || echo MOUNT_FAIL)"
    ).format(mp=mountpoint, opts=NFS_MOUNT_OPTS, remote=remote)
    _, out, err = _ssh_exec(ip, check, timeout=30)
    s = out.strip()
    if "MOUNTED" in s:
        return True
    print("[PREWARM] NFS mount on {0}: {1} ({2})".format(ip, s.strip(), err.strip()[:80]),
          file=sys.stderr)
    return False


def prewarm_worker(ip, model_basename, timeout=PREWARM_TIMEOUT):
    """Prewarm ONE worker: ensure NFS mount, then dd the GGUF through /dev/null
    to populate the OS page cache. Returns (ok, detail)."""
    if not _ensure_nfs_mount(ip):
        return False, "nfs-mount-missing"
    # The NFS export from node0 is /mnt/ssd/models, mounted directly at
    # MODEL_MOUNT_ON_WORKER (/mnt/nano-ssd), so the GGUF sits at
    # /mnt/nano-ssd/<basename> (no extra "models/" segment).
    gguf = "{0}/{1}".format(MODEL_MOUNT_ON_WORKER.rstrip("/"), model_basename)
    # `dd` through /dev/null touches every page -> forces OS to cache the file.
    # `status=progress` is suppressed (we capture only the final summary line).
    cmd = (
        "if [ -f '{gguf}' ]; then "
        "dd if='{gguf}' of=/dev/null bs={bs} 2>/dev/null && echo PREWARM_OK || echo PREWARM_FAIL; "
        "else echo NO_FILE; fi"
    ).format(gguf=gguf, bs=PREWARM_BS)
    _, out, err = _ssh_exec(ip, cmd, timeout=timeout)
    s = out.strip()
    if "PREWARM_OK" in s:
        return True, "ok"
    if "NO_FILE" in s:
        return False, "model-not-on-nfs"
    return False, s or err.strip()[:80]


def prewarm_all(model_path, ips=None, timeout=PREWARM_TIMEOUT, verbose=True):
    """Prewarm every worker (default: all 11 nodes) for the given GGUF.

    model_path is the PC-side path (e.g. C:\\Models\\X.gguf); we only need its
    basename because the workers read the SAME file from their NFS mount of
    node0's SSD. node0 itself does not need prewarming (it serves the SSD
    locally, not over NFS).

    Returns a dict {ip: (ok, detail)}. Best-effort: failures are reported but
    do not raise, so the caller can proceed with inference regardless.
    """
    ips = ips or NODE_IPS
    basename = os.path.basename(model_path)
    results = {}
    if verbose:
        print("[PREWARM] prewarming {0} on {1} node(s) ...".format(basename, len(ips)),
              file=sys.stderr)
    t0 = time.time()
    for ip in ips:
        ok, detail = prewarm_worker(ip, basename, timeout=timeout)
        results[ip] = (ok, detail)
        if verbose:
            tag = "OK " if ok else "WARN"
            print("[PREWARM] {0} {1}: {2}".format(tag, ip, detail), file=sys.stderr)
    if verbose:
        dt = time.time() - t0
        n_ok = sum(1 for ok, _ in results.values() if ok)
        print("[PREWARM] done in {0:.1f}s ({1}/{2} nodes cached)".format(dt, n_ok, len(ips)),
              file=sys.stderr)
    return results


if __name__ == "__main__":
    # Standalone: prewarm a model across the fleet.
    import argparse
    ap = argparse.ArgumentParser(description="Prewarm SSD model weights on cluster workers.")
    ap.add_argument("--model", required=True, help="GGUF model path (basename used on NFS)")
    ap.add_argument("--nodes", default="all", help="single IP, comma list, or 'all'")
    args = ap.parse_args()
    if args.nodes == "all":
        target = NODE_IPS
    else:
        target = [p.strip() for p in args.nodes.split(",") if p.strip()]
    prewarm_all(args.model, ips=target)
