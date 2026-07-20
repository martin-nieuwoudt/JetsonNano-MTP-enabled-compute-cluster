#!/usr/bin/env python3
"""
dl_generic_model.py — Resumable, range-segmented model downloader (PC side).

Mirrors the proven dl_llama_pc.py / fetch_qwen_all_pc.py approach: split the file into
N segments, launch them staggered, retry on failure, concatenate at the end. Used by the
MCP server's model_download tool so any registry model can be fetched reproducibly.

After a successful download it writes a sha256 sidecar next to the output:
    <out>.sha256   ->   "<hexhash>  <basename>"
This is the EXACT naming/format the QoS preflight check (cluster_qos.preflight_model_hash)
expects, so the integrity layer can fire automatically. Disable with --no-sha256.

Usage:
  python dl_generic_model.py --url <hf_resolve_url> --out <path> [--segments 8] [--stagger 12]
  python dl_generic_model.py --url <u> --out <p> --no-sha256      # skip sidecar
"""
import os
import sys
import time
import argparse
import hashlib
import threading
import requests

RETRY = 200
HEADERS = {"User-Agent": "Mozilla/5.0"}
_CHUNK = 1 << 20


def _load_token(out_path):
    token = os.environ.get("HF_TOKEN", "")
    tf = os.path.join(os.path.dirname(out_path) or ".", ".hf_token")
    if not token and os.path.exists(tf):
        token = open(tf, encoding="utf-8").read().strip()
    return token


def _auth_headers(token):
    h = dict(HEADERS)
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def _probe_size(url, headers):
    try:
        r = requests.head(url, headers=headers, allow_redirects=True, timeout=60)
        return int(r.headers.get("Content-Length", 0))
    except Exception as e:  # noqa: BLE001
        print(f"HEAD probe failed: {e}", flush=True)
        return 0


def _attempt_seg(url, out_part, start, end, headers, cur, attempt):
    h = dict(headers)
    h["Range"] = f"bytes={start + cur}-{end}"
    try:
        with requests.get(url, headers=h, stream=True, allow_redirects=True,
                          timeout=120) as r:
            if r.status_code not in (200, 206):
                print(f"seg HTTP {r.status_code} (attempt {attempt})", flush=True)
                return False
            mode = "ab" if cur > 0 else "wb"
            with open(out_part, mode) as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    if chunk:
                        f.write(chunk)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"seg err: {e} (attempt {attempt})", flush=True)
        return False


def download_seg(url, out_part, start, end, headers):
    want = end - start + 1
    for attempt in range(1, RETRY + 1):
        cur = os.path.getsize(out_part) if os.path.exists(out_part) else 0
        if cur >= want:
            print("seg done", flush=True)
            return True
        if not _attempt_seg(url, out_part, start, end, headers, cur, attempt):
            time.sleep(8)
            continue
        now = os.path.getsize(out_part) if os.path.exists(out_part) else 0
        if now >= want:
            print("seg done", flush=True)
            return True
        time.sleep(8)
    print("seg FAILED", flush=True)
    return False


def _sha256_file(path):
    """Stream the file and return its hex sha256 (memory-safe for multi-GB GGUFs)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            c = f.read(_CHUNK)
            if not c:
                break
            h.update(c)
    return h.hexdigest()


def _write_sidecar(out_path, digest):
    """Write '<digest>  <basename>' — the format cluster_qos.preflight_model_hash reads."""
    sidecar = f"{out_path}.sha256"
    base = os.path.basename(out_path)
    tmp = sidecar + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(f"{digest}  {base}\n")
    os.replace(tmp, sidecar)
    return sidecar


def _run_download(url, out_path, segments, stagger, headers, total):
    """Launch staggered segment threads, join, concatenate. Returns True on success."""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    seg = (total + segments - 1) // segments
    parts = [f"{out_path}.part.{i}" for i in range(segments)]
    print(f"Total {total} bytes, {segments} segments of {seg}.", flush=True)

    threads = []
    for i in range(segments):
        s = i * seg
        e = min(s + seg - 1, total - 1)
        t = threading.Thread(target=download_seg, args=(url, parts[i], s, e, headers))
        t.start()
        threads.append(t)
        time.sleep(stagger)

    for t in threads:
        t.join()

    if any(t.is_alive() for t in threads):
        print("SOME SEGMENTS FAILED", flush=True)
        return False

    print("Concatenating...", flush=True)
    with open(out_path, "wb") as o:
        for p in parts:
            with open(p, "rb") as f:
                while True:
                    c = f.read(_CHUNK)
                    if not c:
                        break
                    o.write(c)
            os.remove(p)
    sz = os.path.getsize(out_path)
    if sz != total:
        print(f"Final size: {sz} (expected {total})")
        print("SIZE MISMATCH")
        return False
    print(f"Final size: {sz} (expected {total}) SIZE OK")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--segments", type=int, default=8)
    ap.add_argument("--stagger", type=int, default=12)
    ap.add_argument("--no-sha256", action="store_true",
                    help="skip writing the <out>.sha256 sidecar after download")
    args = ap.parse_args()

    token = _load_token(args.out)
    headers = _auth_headers(token)
    total = _probe_size(args.url, headers)
    if total == 0:
        print("Could not determine file size; aborting.", flush=True)
        sys.exit(1)

    # Strict resumability: if the final file already exists at full size AND a
    # matching sidecar is present, skip the whole download (idempotent re-run).
    if (os.path.exists(args.out) and os.path.getsize(args.out) == total
            and (args.no_sha256 or os.path.exists(f"{args.out}.sha256"))):
        print(f"Already complete: {args.out} ({total} bytes). Nothing to do.", flush=True)
        sys.exit(0)

    if not _run_download(args.url, args.out, args.segments, args.stagger, headers, total):
        sys.exit(1)

    if args.no_sha256:
        print("sha256 sidecar skipped (--no-sha256).")
        sys.exit(0)

    print("Computing sha256...", flush=True)
    digest = _sha256_file(args.out)
    sidecar = _write_sidecar(args.out, digest)
    print(f"sha256: {digest}")
    print(f"sidecar written: {sidecar}")


if __name__ == "__main__":
    main()
