#!/usr/bin/env python3
"""
llm_client.py — Thin client to the cluster-hosted large model (DeepSeek-R1-Distill-Qwen-32B
sharded across all 11 Jetson nodes via llama.cpp RPC).

This is the production plug-in for the orchestrator's Stage 1 (strategy) and
Stage 3 (judge prose) big-model calls. It talks to the persistent llama-server
on http://127.0.0.1:8080 (started by cluster_server.py with the 32B).

Single source of truth for the endpoint lives here; the orchestrator imports
this module rather than hardcoding URLs.
"""
from __future__ import annotations

import json
import urllib.request

LLM_HOST = "127.0.0.1"
LLM_PORT = 8080
COMPLETION_URL = f"http://{LLM_HOST}:{LLM_PORT}/completion"


def complete(prompt: str, n_predict: int = 1024, temperature: float = 0.7,
             timeout: int = 300) -> str:
    """Send a prompt to the 32B and return the generated text (content only)."""
    body = json.dumps({
        "prompt": prompt,
        "n_predict": n_predict,
        "temperature": temperature,
        "cache_prompt": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        COMPLETION_URL, data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        resp = json.loads(r.read().decode("utf-8"))
    return resp.get("content", "")


def is_available() -> bool:
    """True if the 32B server is up and answering /health."""
    try:
        with urllib.request.urlopen(
                f"http://{LLM_HOST}:{LLM_PORT}/health", timeout=3) as r:
            return r.status == 200
    except Exception:
        return False


if __name__ == "__main__":
    print(complete("Reply with the single word: PONG", n_predict=8))
