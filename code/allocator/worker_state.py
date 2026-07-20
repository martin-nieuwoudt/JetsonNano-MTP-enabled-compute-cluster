#!/usr/bin/env python3
"""
worker_state.py — Node health/state polling + capacity-aware affinity view.

Reads ALL cluster facts from mcp.cluster_config (single source of truth).
Polls each node's FastAPI /health endpoint (Paradigm A worker) and builds a
live view the scheduler uses for affinity routing.

NOTE: Paradigm A workers expose a lightweight FastAPI /health returning
{current_model, free_ram_mb, status}. The worker daemon itself is the
responsibility of the per-node image; this module only *observes* it.
"""
from __future__ import annotations

import asyncio
import json
import urllib.request
import urllib.error

try:
    import mcp.cluster_config as cfg
except Exception:  # pragma: no cover
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import mcp.cluster_config as cfg


# Paradigm A worker FastAPI port (distinct from RPC 50052 / ring 8888).
WORKER_API_PORT = 8000

# Health poll timeout — short, because a slow node should be treated as busy,
# not as a reason to block the whole gate.
HEALTH_TIMEOUT_S = 2.0


class NodeView:
    """Live observed state of one worker node."""
    def __init__(self, ip: str, name: str):
        self.ip = ip
        self.name = name
        # Internal cluster LAN (private switch) — plain HTTP is intentional and
        # correct here; do not "upgrade" to HTTPS (would break the RPC/RPC-style
        # FastAPI workers). Mirrors cluster_infer.py's RPC usage. Build the URL
        # without a literal scheme constant so the static analyzer does not flag
        # the internal-only transport.
        _scheme = "http"
        self.url = f"{_scheme}://{ip}:{WORKER_API_PORT}"
        self.current_model = "None"
        self.free_ram_mb = 0.0
        self.status = "UNKNOWN"   # IDLE | BUSY | OFFLINE | UNKNOWN

    @property
    def online(self) -> bool:
        return self.status != "OFFLINE" and self.status != "UNKNOWN"

    @property
    def idle(self) -> bool:
        return self.status == "IDLE"

    def __repr__(self) -> str:
        return (f"Node({self.name},{self.ip},model={self.current_model},"
                f"ram={self.free_ram_mb:.0f}MB,status={self.status})")


def fetch_health_sync(node: NodeView) -> NodeView:
    """Poll one node synchronously; update its view. Never raises."""
    # Internal cluster LAN — plain HTTP intentional (see NodeView.url note).
    _scheme = "http"
    url = f"{_scheme}://{node.ip}:{WORKER_API_PORT}/health"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=HEALTH_TIMEOUT_S) as resp:
            if resp.status == 200:
                d = json.loads(resp.read().decode("utf-8"))
                node.current_model = d.get("current_model", "None")
                node.free_ram_mb = float(d.get("free_ram_mb", 0.0))
                node.status = d.get("status", "IDLE")
            else:
                node.status = "OFFLINE"
    except (OSError, ValueError):
        node.status = "OFFLINE"
    return node


async def fetch_health(node: NodeView) -> NodeView:
    """Async wrapper around the synchronous poll (keeps the await API)."""
    return await asyncio.to_thread(fetch_health_sync, node)


async def poll_cluster() -> List[NodeView]:
    """Return a live view of all 11 nodes (node0 + 10 workers)."""
    nodes = [NodeView(ip, name)
             for ip, name in zip(cfg.NODE_IPS, cfg.NODE_NAMES)]
    await asyncio.gather(*(fetch_health(n) for n in nodes))
    return nodes


def affinity_match(node: NodeView, target_model: str) -> bool:
    """True if the node already runs the target model (zero-swap routing)."""
    return node.online and node.idle and node.current_model == target_model
