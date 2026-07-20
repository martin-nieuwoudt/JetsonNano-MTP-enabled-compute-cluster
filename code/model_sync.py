#!/usr/bin/env python3
"""
model_sync.py — Registry-driven model sync wrapper (PC side).

Single entry point for all model operations. Replaces the redundant per-model
download scripts (dl_llama_pc.py, dl_node0.py, fetch_qwen_all_pc.py,
fetch_qwen_part0_pc.py) by resolving everything from the SINGLE SOURCE OF TRUTH
in mcp.cluster_config.MODELS. No URL, path, or size is hardcoded here.

Subcommands:
  download <key> [--segments N] [--stagger S] [--no-sha256]
      Resumable, range-segmented download via dl_generic_model.py.
  verify <key>
      Local sha256 of the PC GGUF vs its <basename>.gguf.sha256 sidecar.
  push <key> [--host <ip>]
      SCP the GGUF + sidecar to node0's SSD model dir (the NFS model store).

Examples:
  python model_sync.py download qwen2.5-72b-iq3_m
  python model_sync.py verify codestral-22b-q8_0
  python model_sync.py push deepseek-coder-v2-lite-q4_k_m
"""
import os
import sys
import argparse
import hashlib
import subprocess

# Import the single source of truth. Fall back gracefully if run from a context
# where the package import fails (mirrors the try/except pattern in other modules).
try:
    import mcp.cluster_config as cfg
except Exception:  # noqa: BLE001
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import mcp.cluster_config as cfg


def _sha256_file(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def cmd_download(args):
    m = cfg.model_entry(args.key)
    generic = os.path.join(cfg.CODE_DIR, "dl_generic_model.py")
    if not os.path.exists(generic):
        print(f"ERROR: generic downloader missing: {generic}", file=sys.stderr)
        return 2
    argv = [sys.executable, generic,
            "--url", m["hf_url"],
            "--out", m["local"],
            "--segments", str(args.segments),
            "--stagger", str(args.stagger)]
    if args.no_sha256:
        argv.append("--no-sha256")
    # Forward to the engine; it emits the sidecar on success.
    return subprocess.call(argv)


def cmd_verify(args):
    m = cfg.model_entry(args.key)
    out = m["local"]
    sidecar = f"{out}.sha256"
    if not os.path.exists(out):
        print(f"MISSING: {out}", file=sys.stderr)
        return 1
    if not os.path.exists(sidecar):
        print(f"NO SIDECAR: {sidecar} (cannot verify)", file=sys.stderr)
        return 1
    with open(sidecar, "r", encoding="utf-8") as fh:
        exp = fh.read().strip().split()[0].lower()
    got = _sha256_file(out)
    if got == exp:
        print(f"VERIFY OK: {out}")
        print(f"sha256: {got}")
        return 0
    print(f"VERIFY MISMATCH: {out}", file=sys.stderr)
    print(f"  expected {exp}", file=sys.stderr)
    print(f"  got      {got}", file=sys.stderr)
    return 1


def cmd_push(args):
    m = cfg.model_entry(args.key)
    out = m["local"]
    sidecar = f"{out}.sha256"
    if not os.path.exists(out):
        print(f"MISSING: {out} (download first)", file=sys.stderr)
        return 1
    host = args.host or cfg.MODEL_NODE_IP
    remote_dir = cfg.MODEL_DIR_ON_NODE0
    ssh_base = [cfg.SSH_USER + "@" + host] + cfg.SSH_OPTS
    # Ensure remote dir exists, then SCP the GGUF and its sidecar.
    subprocess.call(["ssh"] + ssh_base +
                    [f"mkdir -p {remote_dir} && echo ready"])
    rc1 = subprocess.call(
        ["scp"] + cfg.SSH_OPTS + [out, f"{cfg.SSH_USER}@{host}:{remote_dir}/"])
    rc2 = 0
    if os.path.exists(sidecar):
        rc2 = subprocess.call(
            ["scp"] + cfg.SSH_OPTS + [sidecar, f"{cfg.SSH_USER}@{host}:{remote_dir}/"])
    if rc1 != 0 or rc2 != 0:
        print("PUSH FAILED (see scp errors above)", file=sys.stderr)
        return 1
    print(f"PUSH OK: {out} -> {host}:{remote_dir}/")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Registry-driven model sync (PC side).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_dl = sub.add_parser("download", help="resumable download via dl_generic_model.py")
    p_dl.add_argument("key", help="model registry key, e.g. qwen2.5-72b-iq3_m")
    p_dl.add_argument("--segments", type=int, default=8)
    p_dl.add_argument("--stagger", type=int, default=12)
    p_dl.add_argument("--no-sha256", action="store_true",
                      help="skip writing the <out>.sha256 sidecar")
    p_dl.set_defaults(func=cmd_download)

    p_v = sub.add_parser("verify", help="sha256 vs sidecar")
    p_v.add_argument("key")
    p_v.set_defaults(func=cmd_verify)

    p_p = sub.add_parser("push", help="SCP GGUF + sidecar to node0 SSD")
    p_p.add_argument("key")
    p_p.add_argument("--host", default=None, help="override target host IP")
    p_p.set_defaults(func=cmd_push)

    args = ap.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
