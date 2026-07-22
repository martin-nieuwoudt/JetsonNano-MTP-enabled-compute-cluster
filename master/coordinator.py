"""
Master coordinator for the Jetson Nano MTP-enabled compute cluster.

Architecture
------------
The coordinator is the hub of the star topology.  It:

* Accepts :class:`~shared.protocol.MessageType.REGISTER` messages from worker
  nodes and maintains a live registry.
* Monitors node liveness via heartbeat timeouts.
* Accepts task-submission requests (via TCP) and forwards them to an
  appropriate online worker.
* Returns results to the original submitter.

Usage (Windows Master PC)::

    python -m master.coordinator

The coordinator binds to ``0.0.0.0`` by default so that all Nano nodes on the
1 Gbps star network can reach it.
"""

from __future__ import annotations

import logging
import socket
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from shared.config import (
    MASTER_HOST,
    MASTER_PORT,
    SOCKET_TIMEOUT,
    TASK_TIMEOUT,
    WORKER_HEARTBEAT_TIMEOUT,
)
from shared.protocol import (
    Message,
    MessageType,
    NodeStatus,
    TaskType,
    recv_message,
    send_message,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node record
# ---------------------------------------------------------------------------


@dataclass
class NodeRecord:
    """Runtime record for a single registered Jetson Nano worker."""

    node_id: str
    host: str
    worker_port: int
    rpc_port: int                # llama.cpp RPC server port on the Nano
    pycuda_port: int             # PyCUDA task server port on the Nano
    status: NodeStatus = NodeStatus.ONLINE
    last_heartbeat: float = field(default_factory=time.monotonic)
    active_task_id: Optional[str] = None

    @property
    def rpc_endpoint(self) -> str:
        """Return ``host:rpc_port`` string used by llama.cpp ``--rpc`` flag."""
        return f"{self.host}:{self.rpc_port}"


# ---------------------------------------------------------------------------
# Coordinator
# ---------------------------------------------------------------------------


class Coordinator:
    """Central coordinator running on the Windows Master PC."""

    def __init__(self, host: str = MASTER_HOST, port: int = MASTER_PORT) -> None:
        self.host = host
        self.port = port

        self._nodes: Dict[str, NodeRecord] = {}
        self._nodes_lock = threading.Lock()

        self._pending_results: Dict[str, Optional[dict]] = {}
        self._result_events: Dict[str, threading.Event] = {}
        self._results_lock = threading.Lock()

        self._server_sock: Optional[socket.socket] = None
        self._running = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the coordinator server (blocking)."""
        self._running = True

        # Launch heartbeat watchdog in background
        threading.Thread(target=self._heartbeat_watchdog, daemon=True).start()

        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.port))
        self._server_sock.listen(32)
        logger.info("Coordinator listening on %s:%d", self.host, self.port)

        try:
            while self._running:
                try:
                    client_sock, addr = self._server_sock.accept()
                except OSError:
                    break
                threading.Thread(
                    target=self._handle_connection,
                    args=(client_sock, addr),
                    daemon=True,
                ).start()
        finally:
            self._server_sock.close()

    def stop(self) -> None:
        """Signal the coordinator to shut down."""
        self._running = False
        if self._server_sock:
            self._server_sock.close()

    # ------------------------------------------------------------------
    # Node queries
    # ------------------------------------------------------------------

    def online_nodes(self) -> List[NodeRecord]:
        """Return a snapshot of all currently online worker nodes."""
        with self._nodes_lock:
            return [n for n in self._nodes.values() if n.status != NodeStatus.OFFLINE]

    def rpc_endpoints(self) -> List[str]:
        """Return llama.cpp RPC endpoint strings for all online nodes."""
        return [n.rpc_endpoint for n in self.online_nodes()]

    # ------------------------------------------------------------------
    # Task submission
    # ------------------------------------------------------------------

    def submit_task(
        self, task_type: TaskType, payload: dict, timeout: float = TASK_TIMEOUT
    ) -> Optional[dict]:
        """
        Dispatch a task to an available worker and wait for the result.

        Parameters
        ----------
        task_type:
            Either :attr:`~shared.protocol.TaskType.LLM_INFERENCE` or
            :attr:`~shared.protocol.TaskType.PYCUDA`.
        payload:
            Task-specific data forwarded verbatim to the worker.
        timeout:
            Maximum seconds to wait for a result.

        Returns
        -------
        dict
            The ``result`` dict returned by the worker, or ``None`` on timeout.
        """
        node = self._pick_node()
        if node is None:
            raise RuntimeError("No online worker nodes available")

        task_id = str(uuid.uuid4())
        event = threading.Event()

        with self._results_lock:
            self._pending_results[task_id] = None
            self._result_events[task_id] = event

        # Mark node as busy
        with self._nodes_lock:
            node.status = NodeStatus.BUSY
            node.active_task_id = task_id

        # Forward to worker
        threading.Thread(
            target=self._dispatch_to_worker,
            args=(node, task_id, task_type, payload),
            daemon=True,
        ).start()

        event.wait(timeout=timeout)

        with self._results_lock:
            result = self._pending_results.pop(task_id, None)
            self._result_events.pop(task_id, None)

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _pick_node(self) -> Optional[NodeRecord]:
        """Select an online (non-busy) node; fall back to least-busy."""
        with self._nodes_lock:
            online = [n for n in self._nodes.values() if n.status == NodeStatus.ONLINE]
            if online:
                return online[0]
            # Fall back: accept a busy node (queue at worker side)
            any_up = [
                n for n in self._nodes.values() if n.status != NodeStatus.OFFLINE
            ]
            return any_up[0] if any_up else None

    def _dispatch_to_worker(
        self,
        node: NodeRecord,
        task_id: str,
        task_type: TaskType,
        payload: dict,
    ) -> None:
        """Connect to a worker and send a TASK_SUBMIT message."""
        try:
            sock = socket.create_connection(
                (node.host, node.worker_port), timeout=SOCKET_TIMEOUT
            )
            sock.settimeout(SOCKET_TIMEOUT)
            msg = Message(
                type=MessageType.TASK_SUBMIT,
                payload={
                    "task_id": task_id,
                    "task_type": task_type,
                    "data": payload,
                },
            )
            send_message(sock, msg)
            response = recv_message(sock)
            sock.close()

            with self._nodes_lock:
                node.status = NodeStatus.ONLINE
                node.active_task_id = None

            if response.type == MessageType.TASK_RESULT:
                with self._results_lock:
                    self._pending_results[task_id] = response.payload.get("result")
                    evt = self._result_events.get(task_id)
                if evt:
                    evt.set()
            else:
                logger.error("Worker returned unexpected message: %s", response.type)
                with self._results_lock:
                    evt = self._result_events.get(task_id)
                if evt:
                    evt.set()

        except Exception as exc:
            logger.exception("Failed to dispatch task %s to %s: %s", task_id, node.node_id, exc)
            with self._nodes_lock:
                node.status = NodeStatus.ONLINE
                node.active_task_id = None
            with self._results_lock:
                evt = self._result_events.get(task_id)
            if evt:
                evt.set()

    def _handle_connection(
        self, sock: socket.socket, addr: tuple
    ) -> None:
        """Handle an incoming connection from a worker or task submitter."""
        sock.settimeout(SOCKET_TIMEOUT)
        try:
            msg = recv_message(sock)
            if msg.type == MessageType.REGISTER:
                self._handle_register(sock, addr, msg)
            elif msg.type == MessageType.HEARTBEAT:
                self._handle_heartbeat(sock, msg)
            elif msg.type == MessageType.DEREGISTER:
                self._handle_deregister(msg)
            elif msg.type == MessageType.TASK_RESULT:
                self._handle_task_result(msg)
            elif msg.type == MessageType.NODE_LIST:
                self._handle_node_list(sock)
            else:
                logger.warning("Unknown message type from %s: %s", addr, msg.type)
        except Exception as exc:
            logger.debug("Connection error from %s: %s", addr, exc)
        finally:
            sock.close()

    def _handle_register(
        self, sock: socket.socket, addr: tuple, msg: Message
    ) -> None:
        p = msg.payload
        node_id = p.get("node_id", str(uuid.uuid4()))
        host = p.get("host", addr[0])
        record = NodeRecord(
            node_id=node_id,
            host=host,
            worker_port=p["worker_port"],
            rpc_port=p["rpc_port"],
            pycuda_port=p["pycuda_port"],
        )
        with self._nodes_lock:
            self._nodes[node_id] = record
        logger.info("Registered node %s at %s (RPC :%d)", node_id, host, record.rpc_port)
        send_message(
            sock,
            Message(
                type=MessageType.REGISTER_ACK,
                payload={"node_id": node_id, "status": "ok"},
            ),
        )

    def _handle_heartbeat(self, sock: socket.socket, msg: Message) -> None:
        node_id = msg.payload.get("node_id")
        with self._nodes_lock:
            if node_id in self._nodes:
                self._nodes[node_id].last_heartbeat = time.monotonic()
                if self._nodes[node_id].status == NodeStatus.OFFLINE:
                    self._nodes[node_id].status = NodeStatus.ONLINE
                    logger.info("Node %s came back online", node_id)
        send_message(sock, Message(type=MessageType.HEARTBEAT_ACK))

    def _handle_deregister(self, msg: Message) -> None:
        node_id = msg.payload.get("node_id")
        with self._nodes_lock:
            if node_id in self._nodes:
                self._nodes[node_id].status = NodeStatus.OFFLINE
                logger.info("Node %s deregistered", node_id)

    def _handle_task_result(self, msg: Message) -> None:
        task_id = msg.payload.get("task_id")
        with self._results_lock:
            if task_id in self._pending_results:
                self._pending_results[task_id] = msg.payload.get("result")
                evt = self._result_events.get(task_id)
                if evt:
                    evt.set()

    def _handle_node_list(self, sock: socket.socket) -> None:
        nodes = [
            {
                "node_id": n.node_id,
                "host": n.host,
                "rpc_port": n.rpc_port,
                "status": n.status,
            }
            for n in self._nodes.values()
        ]
        send_message(
            sock,
            Message(type=MessageType.NODE_LIST, payload={"nodes": nodes}),
        )

    def _heartbeat_watchdog(self) -> None:
        """Background thread: mark nodes as offline if heartbeats are missed."""
        while self._running:
            now = time.monotonic()
            with self._nodes_lock:
                for node in self._nodes.values():
                    if node.status != NodeStatus.OFFLINE:
                        elapsed = now - node.last_heartbeat
                        if elapsed > WORKER_HEARTBEAT_TIMEOUT:
                            node.status = NodeStatus.OFFLINE
                            logger.warning(
                                "Node %s timed out (%.1fs without heartbeat)",
                                node.node_id,
                                elapsed,
                            )
            time.sleep(1)


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    coordinator = Coordinator()
    try:
        coordinator.start()
    except KeyboardInterrupt:
        logger.info("Shutting down coordinator")
        coordinator.stop()


if __name__ == "__main__":
    main()
