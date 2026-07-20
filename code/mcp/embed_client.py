#!/usr/bin/env python3
"""
embed_client.py — PC-side client for the FP16 embedding worker tier.

This is the "instructions in FP16" path to the small models.

The small LLMs (Gemma 4 E4B, Phi-3, Qwythos-9B, ...) are LLMs and therefore
receive TEXT instructions via the orchestrator. What this module adds is the
*companion* FP16 payload: the orchestrator tokenizes the instruction text,
streams the token-ids to the embedding workers (port 9998, float16 projection
kernel), and gets back a float16 embedding matrix. That matrix is attached to
the task the agent receives — a structured FP16 seed/context vector alongside
the text.

Reuses the canonical distribution transport from cluster_mcp_server
(_embed_distribute / _tcp_up) so there is exactly one wire implementation.
All changeable facts (ports, dims, vocab) come from cluster_config.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import importlib
import os
import re
import subprocess
import sys

import numpy as np

# Single source of truth for ports/dims/vocab.
try:
    import cluster_config as cfg
except Exception:  # pragma: no cover
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import cluster_config as cfg

# llama.cpp tokenizer binary (pinned commit b56f079e2). Uses each model's OWN
# vocab from its GGUF — no Python tokenizer libs needed. This is the real
# tokenizer the model actually uses, so the FP16 embeddings are semantically
# grounded in the model's token space.
_TOKENIZER_BIN = r"C:\llama.cpp\build\bin\llama-tokenize.exe"
_TOKEN_LIST_RE = re.compile(r"\[[\d, ]+\]")


def _tokenize_via_bin(model_path: str, text: str) -> list[int] | None:
    """Call llama-tokenize.exe for a GGUF and parse the [id, id, ...] output."""
    if not os.path.exists(_TOKENIZER_BIN) or not os.path.exists(model_path):
        return None
    try:
        r = subprocess.run(
            [_TOKENIZER_BIN, "--model", model_path, "--prompt", text, "--ids"],
            capture_output=True, text=True, timeout=120,
        )
        m = _TOKEN_LIST_RE.search(r.stdout)
        if not m:
            return None
        return [int(x) for x in m.group(0)[1:-1].split(",") if x.strip()]
    except Exception:  # noqa: BLE001
        return None


def _fallback_tokenize(text: str, vocab_size: int | None = None) -> list[int]:
    """Deterministic whitespace tokenizer -> token-ids in [0, vocab_size).
    Used only when the real tokenizer binary/model is unavailable, so the FP16
    path never hard-fails. NOT semantically meaningful — a safety net only."""
    if vocab_size is None:
        vocab_size = cfg.VOCAB_SIZE
    toks = []
    for w in text.split():
        h = hashlib.md5(w.encode("utf-8")).digest()
        toks.append(int.from_bytes(h[:4], "big") % vocab_size)
    if not toks:
        toks = [0]
    return toks


def tokenize(text: str, model_key: str | None = None) -> np.ndarray:
    """Tokenize `text` into an int32 token-id array using the REAL model vocab.

    Resolution order (single source of truth = cluster_config.TOKENIZER_MODELS):
      1. If model_key maps to a loadable GGUF, use that model's own tokenizer.
      2. Else if a family fallback GGUF exists (e.g. tiny-qwen for Qwen family),
         use it (same tokenizer family, far smaller/faster to load).
      3. Else fall back to the deterministic mock so the FP16 path still runs.

    The rest of the pipeline is tokenizer-agnostic — it only needs int32 ids.
    """
    vocab_size = cfg.VOCAB_SIZE
    candidates: list[str] = []
    tm = getattr(cfg, "TOKENIZER_MODELS", {})
    if model_key and model_key in tm:
        candidates.append(tm[model_key])
    # Family fallbacks (small GGUFs sharing the tokenizer of bigger models).
    candidates += [p for p in tm.get("_fallbacks", []) if p]
    for path in candidates:
        ids = _tokenize_via_bin(path, text)
        if ids:
            return np.array(ids, dtype=np.int32)
    # Last resort: deterministic mock (keeps FP16 path alive offline).
    return np.array(_fallback_tokenize(text, vocab_size), dtype=np.int32)


def _server_module():
    """Lazily import the canonical transport (avoids building the MCP app at
    import time of this module)."""
    return importlib.import_module("cluster_mcp_server")


def live_embed_targets() -> list[str]:
    """Return IPs of nodes currently running the embedding worker."""
    srv = _server_module()
    return [ip for ip in cfg.NODE_IPS if srv._tcp_up(ip, cfg.EMBED_PORT)]


async def embed_text(text: str, targets: list[str] | None = None,
                model_key: str | None = None) -> np.ndarray | None:
    """Tokenize `text` (real model vocab), stream to embedding workers, return
    float16 matrix shaped (num_tokens, EMBEDDING_DIM). Returns None if no
    workers are live. `model_key` selects which model's tokenizer to use."""
    token_ids = tokenize(text, model_key)
    if targets is None:
        targets = live_embed_targets()
    if not targets:
        return None
    srv = _server_module()
    # _embed_distribute expects a 2D corpus (paragraphs x tokens); wrap as 1 row.
    corpus = token_ids.reshape(1, -1)
    matrix = await srv._embed_distribute(targets, corpus)
    if matrix is None:
        return None
    # We sent 1 row, so the vstacked result is (num_tokens, EMBEDDING_DIM).
    return matrix.astype(np.float16)


def embed_text_sync(text: str, targets: list[str] | None = None,
                    model_key: str | None = None) -> np.ndarray | None:
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(embed_text(text, targets, model_key))
    finally:
        loop.close()


def embedding_to_b64(matrix: np.ndarray) -> str:
    """Serialize a float16 embedding matrix to base64 for JSON transport."""
    return base64.b64encode(matrix.astype(np.float16).tobytes()).decode("ascii")


def embedding_from_b64(b64: str, num_tokens: int) -> np.ndarray:
    raw = base64.b64decode(b64)
    return np.frombuffer(raw, dtype=np.float16).reshape(num_tokens, cfg.EMBEDDING_DIM)


if __name__ == "__main__":
    txt = sys.argv[1] if len(sys.argv) > 1 else "test instruction payload"
    emb = embed_text_sync(txt)
    if emb is None:
        print("No embedding workers live (start them via embed_start_workers).")
        sys.exit(2)
    print(f"text: {txt!r}")
    print(f"tokens: {tokenize(txt).tolist()}")
    print(f"fp16 embedding shape: {emb.shape}  dtype={emb.dtype}")
    print(f"b64 len: {len(embedding_to_b64(emb))}")
