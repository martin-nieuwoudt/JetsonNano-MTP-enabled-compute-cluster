#!/usr/bin/env python3
"""
Cluster health-check utility.

Connects to the Master PC coordinator and prints the status of all registered
Jetson Nano worker nodes, including whether their llama.cpp RPC server ports
are reachable.

Usage::

    python scripts/health_check.py --master-host 192.168.1.1 --master-port 7000
"""

from __future__ import annotations

import argparse
import socket
import sys
import time
from typing import List

# Allow running from repo root without installing the package
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.config import MASTER_HOST, MASTER_PORT, SOCKET_TIMEOUT
from shared.protocol import Message, MessageType, recv_message, send_message


def _probe_port(host: str, port: int, timeout: float = 2.0) -> bool:
    """Return True if *host*:*port* accepts a TCP connection."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError):
        return False


def fetch_node_list(master_host: str, master_port: int) -> List[dict]:
    """Request the node list from the coordinator."""
    sock = socket.create_connection((master_host, master_port), timeout=SOCKET_TIMEOUT)
    send_message(sock, Message(type=MessageType.NODE_LIST))
    resp = recv_message(sock)
    sock.close()
    if resp.type != MessageType.NODE_LIST:
        raise RuntimeError(f"Unexpected response: {resp.type}")
    return resp.payload.get("nodes", [])


def main() -> None:
    parser = argparse.ArgumentParser(description="Cluster health check")
    parser.add_argument("--master-host", default=MASTER_HOST)
    parser.add_argument("--master-port", type=int, default=MASTER_PORT)
    args = parser.parse_args()

    print(f"Connecting to coordinator at {args.master_host}:{args.master_port}...")
    try:
        nodes = fetch_node_list(args.master_host, args.master_port)
    except Exception as exc:
        print(f"ERROR: Could not reach coordinator: {exc}", file=sys.stderr)
        sys.exit(1)

    if not nodes:
        print("No nodes registered with the coordinator.")
        return

    print(f"\n{'NODE ID':<20} {'HOST':<16} {'STATUS':<10} {'RPC PORT':<10} {'RPC REACHABLE'}")
    print("-" * 70)
    for node in nodes:
        node_id = node.get("node_id", "?")
        host = node.get("host", "?")
        status = node.get("status", "?")
        rpc_port = node.get("rpc_port", 50052)
        rpc_ok = _probe_port(host, rpc_port)
        rpc_label = "✓" if rpc_ok else "✗"
        print(f"{node_id:<20} {host:<16} {status:<10} {rpc_port:<10} {rpc_label}")

    online = sum(1 for n in nodes if n.get("status") == "online")
    print(f"\n{online}/{len(nodes)} nodes online.")


if __name__ == "__main__":
    main()
