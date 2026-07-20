#!/usr/bin/env python3
"""
persist_nfs_fstab.py — make the model-SSD NFS mount boot-persistent on workers
================================================================================
The prewarm path (`prewarm_nfs.py`) already mounts the NFS share on demand at
runtime, but that mount is lost on reboot. This script writes an idempotent
`fstab` entry on every WORKER (192.168.50.151-160) so the mount comes back
automatically after a reboot — without blocking boot if node0 is momentarily
unavailable.

Design choices (why):
  - `noauto,x-systemd.automount` : the mount is performed lazily on FIRST ACCESS
    (e.g. when prewarm or inference touches /mnt/nano-ssd), not at boot. This
    prevents a worker from hanging at the boot prompt waiting for node0's NFS.
  - `_netdev`  : tells systemd the mount depends on the network being up.
  - `nofail`   : a missing/unreachable node0 must NOT fail the boot.
  - `nolock,vers=3,ro` : the proven Jetson NFS client options (matches the
    runtime mount used by prewarm_nfs._ensure_nfs_mount).

node0 (.150) is the EXPORTER and is deliberately excluded — it does not mount
its own SSD over NFS.

Idempotent: re-running only adds the line if it is not already present (matched
by mount-point + remote export), so it is safe to run repeatedly.
"""

import os
import sys
import paramiko

HERE = os.path.dirname(os.path.abspath(__file__))

# --- AUTHORITATIVE CONFIG (single source of truth: mcp/cluster_config.py) ----
try:
    import mcp.cluster_config as cfg
    SSH_USER = cfg.SSH_USER
    SSH_KEY_PATH = cfg.SSH_KEY_PATH
    NODE_IPS = cfg.NODE_IPS
    MODEL_NODE_IP = cfg.MODEL_NODE_IP
    MODEL_DIR_ON_NODE0 = cfg.MODEL_DIR_ON_NODE0
    MODEL_MOUNT_ON_WORKER = cfg.MODEL_MOUNT_ON_WORKER
except Exception:
    SSH_USER = "jetson"
    SSH_KEY_PATH = r"C:\Users\marti\.ssh\id_ed25519"
    NODE_IPS = [f"192.168.50.{i}" for i in range(150, 161)]
    MODEL_NODE_IP = "192.168.50.150"
    MODEL_DIR_ON_NODE0 = "/mnt/ssd/models"
    MODEL_MOUNT_ON_WORKER = "/mnt/nano-ssd"

# node0 is the exporter — never mount its own share.
WORKER_IPS = [ip for ip in NODE_IPS if ip != MODEL_NODE_IP]

# NFS client options. Keep in sync with prewarm_nfs.NFS_MOUNT_OPTS (minus the
# systemd boot-persistence flags, which only belong in fstab).
FSTAB_OPTS = "nolock,vers=3,ro,noauto,x-systemd.automount,_netdev,nofail"
FSTAB_LINE = "{remote} {mp} nfs {opts} 0 0".format(
    remote="{0}:/{1}".format(MODEL_NODE_IP, MODEL_DIR_ON_NODE0.strip("/")),
    mp=MODEL_MOUNT_ON_WORKER,
    opts=FSTAB_OPTS,
)


def _ssh_exec(ip, cmd, timeout=30):
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


def persist_on_worker(ip):
    """Add the fstab entry (if missing) and reload systemd so automount is
    active. Returns (ok, detail)."""
    # 1) Ensure the local mountpoint exists.
    rc, _, err = _ssh_exec(ip, "sudo mkdir -p {0}".format(MODEL_MOUNT_ON_WORKER))
    if rc != 0:
        return False, "mkdir-fail: {0}".format(err.strip()[:80])

    # 2) Add the fstab line only if an equivalent entry is not already present.
    #    Match on the mount point + remote export so we don't duplicate.
    add_cmd = (
        "grep -qF '{mp}' /etc/fstab && grep -qF '{remote}' /etc/fstab "
        "&& echo ALREADY || "
        "(echo '{line}' | sudo tee -a /etc/fstab >/dev/null && echo ADDED)"
    ).format(mp=MODEL_MOUNT_ON_WORKER,
             remote="{0}:/{1}".format(MODEL_NODE_IP, MODEL_DIR_ON_NODE0.strip("/")),
             line=FSTAB_LINE)
    rc, out, err = _ssh_exec(ip, add_cmd)
    state = out.strip()
    if rc != 0:
        return False, "fstab-fail: {0}".format(err.strip()[:80])
    if state not in ("ALREADY", "ADDED"):
        return False, "fstab-unknown: {0}".format(state or err.strip()[:80])

    # 3) Reload systemd so the new automount unit is picked up. The mount will
    #    then happen lazily on first access (no boot hang).
    _ssh_exec(ip, "sudo systemctl daemon-reload", timeout=30)

    return True, state


def main():
    print("[NFS-FSTAB] target line: {0}".format(FSTAB_LINE), file=sys.stderr)
    print("[NFS-FSTAB] applying to {0} worker(s) ...".format(len(WORKER_IPS)),
          file=sys.stderr)
    results = {}
    for ip in WORKER_IPS:
        ok, detail = persist_on_worker(ip)
        results[ip] = (ok, detail)
        tag = "OK " if ok else "FAIL"
        print("[NFS-FSTAB] {0} {1}: {2}".format(tag, ip, detail), file=sys.stderr)
    n_ok = sum(1 for ok, _ in results.values() if ok)
    print("[NFS-FSTAB] done ({0}/{1} workers persisted)".format(n_ok, len(WORKER_IPS)),
          file=sys.stderr)
    return 0 if n_ok == len(WORKER_IPS) else 1


if __name__ == "__main__":
    sys.exit(main())
