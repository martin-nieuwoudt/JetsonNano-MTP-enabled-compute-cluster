"""
Wire protocol for the Jetson Nano compute cluster.

All messages are JSON-encoded dictionaries transmitted over TCP as
length-prefixed frames:

    [ 4-byte big-endian uint32 body_length ][ body_length bytes of UTF-8 JSON ]

Message schema
--------------
Every message carries a ``type`` field (a string from :class:`MessageType`)
and an optional ``payload`` dict whose keys depend on the message type.
"""

from __future__ import annotations

import json
import socket
import struct
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------


class MessageType(str, Enum):
    # Worker lifecycle
    REGISTER = "REGISTER"           # Worker → Master: announce availability
    REGISTER_ACK = "REGISTER_ACK"  # Master → Worker: confirm registration
    HEARTBEAT = "HEARTBEAT"         # Worker → Master: liveness ping
    HEARTBEAT_ACK = "HEARTBEAT_ACK"  # Master → Worker: pong
    DEREGISTER = "DEREGISTER"       # Worker → Master: graceful shutdown

    # Task dispatch
    TASK_SUBMIT = "TASK_SUBMIT"     # Client/Master → Master/Worker: submit task
    TASK_ACK = "TASK_ACK"          # Worker → Master: task accepted
    TASK_RESULT = "TASK_RESULT"     # Worker → Master/Client: task completed
    TASK_ERROR = "TASK_ERROR"       # Worker → Master/Client: task failed

    # Cluster queries
    NODE_LIST = "NODE_LIST"         # Master → requester: list of online nodes
    NODE_STATUS = "NODE_STATUS"     # Master → requester: status of a single node


class TaskType(str, Enum):
    LLM_INFERENCE = "LLM_INFERENCE"   # llama.cpp RPC-based inference
    PYCUDA = "PYCUDA"                  # PyCUDA kernel execution


class NodeStatus(str, Enum):
    ONLINE = "online"
    BUSY = "busy"
    OFFLINE = "offline"


class TaskResultStatus(str, Enum):
    """Well-known status strings returned in TASK_RESULT payloads."""

    SUCCESS = "success"
    # LLM tasks are handled directly by the llama-rpc-server; the worker
    # returns this status to indicate the RPC endpoint is active.
    RPC_OFFLOADED = "rpc_offloaded"
    ERROR = "error"


# ---------------------------------------------------------------------------
# Message dataclass
# ---------------------------------------------------------------------------


@dataclass
class Message:
    """A single protocol message."""

    type: MessageType
    payload: dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_bytes(self) -> bytes:
        """Serialise the message to a length-prefixed byte frame."""
        body = json.dumps({"type": self.type, "payload": self.payload}).encode("utf-8")
        header = struct.pack(">I", len(body))
        return header + body

    @classmethod
    def from_bytes(cls, data: bytes) -> "Message":
        """Deserialise a message from raw bytes (body only, no header)."""
        obj = json.loads(data.decode("utf-8"))
        return cls(type=MessageType(obj["type"]), payload=obj.get("payload", {}))


# ---------------------------------------------------------------------------
# Socket I/O helpers
# ---------------------------------------------------------------------------


def send_message(sock: socket.socket, msg: Message) -> None:
    """Send *msg* over *sock* using the length-prefix framing protocol."""
    data = msg.to_bytes()
    sock.sendall(data)


def recv_message(sock: socket.socket) -> Message:
    """Receive one message from *sock*, blocking until complete."""
    # Read 4-byte header
    header = _recv_exact(sock, 4)
    body_length = struct.unpack(">I", header)[0]
    body = _recv_exact(sock, body_length)
    return Message.from_bytes(body)


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    """Read exactly *n* bytes from *sock*, raising ``ConnectionError`` on EOF."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Socket closed before all bytes were received")
        buf.extend(chunk)
    return bytes(buf)
