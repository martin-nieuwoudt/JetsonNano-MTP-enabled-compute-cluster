"""
Jetson Nano worker process.

Responsibilities
----------------
1. Register with the Windows Master PC coordinator on start-up.
2. Start the llama.cpp RPC server subprocess.
3. Initialise the PyCUDA executor.
4. Listen for task dispatch messages from the coordinator.
5. Execute tasks (LLM inference is handled by the RPC server; PyCUDA tasks are
   executed by :class:`~worker.pycuda_worker.PyCUDAWorker`).
6. Send heartbeats to keep the coordinator updated on liveness.
7. Deregister and shut down cleanly on ``SIGTERM`` / ``SIGINT``.

Usage (on each Jetson Nano)::

    python -m worker.worker \\
        --master-host 192.168.1.1 \\
        --master-port 7000 \\
        --node-id nano-01 \\
        --worker-port 7010 \\
        --rpc-port 50052 \\
        --pycuda-port 7020

Environment variables
---------------------
``MASTER_HOST``
    Override the master coordinator host.
``MASTER_PORT``
    Override the master coordinator port.
``NODE_ID``
    Override the node identifier.
"""

from __future__ import annotations

import argparse
import logging
import os
import signal
import socket
import threading
import time
import types
import uuid
from typing import Optional

from shared.config import (
    LLAMACPP_RPC_PORT,
    MASTER_CONNECT_DEFAULT,
    MASTER_PORT,
    PYCUDA_TASK_PORT,
    SOCKET_TIMEOUT,
    WORKER_HEARTBEAT_INTERVAL,
    WORKER_LISTEN_HOST,
    WORKER_PORT,
)
from shared.protocol import (
    Message,
    MessageType,
    TaskResultStatus,
    TaskType,
    recv_message,
    send_message,
)
from worker.llm_rpc_server import LLMRPCServer
from worker.pycuda_worker import PyCUDAWorker

logger = logging.getLogger(__name__)


class Worker:
    """
    Jetson Nano compute worker.

    Parameters
    ----------
    master_host:
        IP / hostname of the Windows Master PC coordinator.
    master_port:
        TCP port of the coordinator's registration listener.
    node_id:
        Unique string identifier for this node (e.g. ``"nano-01"``).
    worker_port:
        Local TCP port for receiving task dispatch messages.
    rpc_port:
        Port on which the llama.cpp RPC server will listen.
    pycuda_port:
        Port on which the PyCUDA task server listens (reserved for future
        direct dispatch; currently tasks arrive via *worker_port*).
    """

    def __init__(
        self,
        master_host: str = MASTER_CONNECT_DEFAULT,
        master_port: int = MASTER_PORT,
        node_id: Optional[str] = None,
        worker_port: int = WORKER_PORT,
        rpc_port: int = LLAMACPP_RPC_PORT,
        pycuda_port: int = PYCUDA_TASK_PORT,
    ) -> None:
        self.master_host = master_host
        self.master_port = master_port
        self.node_id = node_id or str(uuid.uuid4())
        self.worker_port = worker_port
        self.rpc_port = rpc_port
        self.pycuda_port = pycuda_port

        self._running = False
        self._rpc_server = LLMRPCServer(port=rpc_port)
        self._pycuda_worker: Optional[PyCUDAWorker] = None
        self._server_sock: Optional[socket.socket] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start all sub-services and enter the main event loop."""
        self._running = True

        # Install signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        # Start llama.cpp RPC server
        try:
            self._rpc_server.start()
        except Exception as exc:
            logger.warning("Could not start llama-rpc-server: %s", exc)

        # Initialise PyCUDA
        try:
            self._pycuda_worker = PyCUDAWorker()
        except Exception as exc:
            logger.warning("Could not initialise PyCUDA: %s", exc)

        # Register with the master coordinator
        self._register()

        # Start heartbeat sender in background
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()

        # Start local task listener
        self._listen_for_tasks()

    def stop(self) -> None:
        """Deregister from the master and shut down all sub-services."""
        if not self._running:
            return
        self._running = False
        self._deregister()
        self._rpc_server.stop()
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass
        logger.info("Worker %s stopped", self.node_id)

    # ------------------------------------------------------------------
    # Registration / heartbeat
    # ------------------------------------------------------------------

    def _register(self) -> None:
        """Send a REGISTER message to the master coordinator."""
        try:
            local_ip = self._get_local_ip()
            sock = socket.create_connection(
                (self.master_host, self.master_port), timeout=SOCKET_TIMEOUT
            )
            send_message(
                sock,
                Message(
                    type=MessageType.REGISTER,
                    payload={
                        "node_id": self.node_id,
                        "host": local_ip,
                        "worker_port": self.worker_port,
                        "rpc_port": self.rpc_port,
                        "pycuda_port": self.pycuda_port,
                    },
                ),
            )
            ack = recv_message(sock)
            sock.close()
            if ack.type == MessageType.REGISTER_ACK:
                logger.info(
                    "Registered with master %s:%d as node %s",
                    self.master_host,
                    self.master_port,
                    self.node_id,
                )
            else:
                logger.warning("Unexpected registration response: %s", ack.type)
        except Exception as exc:
            logger.error("Failed to register with master: %s", exc)

    def _deregister(self) -> None:
        """Notify the master that this node is going offline."""
        try:
            sock = socket.create_connection(
                (self.master_host, self.master_port), timeout=SOCKET_TIMEOUT
            )
            send_message(
                sock,
                Message(
                    type=MessageType.DEREGISTER,
                    payload={"node_id": self.node_id},
                ),
            )
            sock.close()
        except Exception:
            pass

    def _heartbeat_loop(self) -> None:
        """Send periodic heartbeat messages to the master coordinator."""
        while self._running:
            try:
                sock = socket.create_connection(
                    (self.master_host, self.master_port), timeout=SOCKET_TIMEOUT
                )
                send_message(
                    sock,
                    Message(
                        type=MessageType.HEARTBEAT,
                        payload={"node_id": self.node_id},
                    ),
                )
                recv_message(sock)
                sock.close()
            except Exception as exc:
                logger.debug("Heartbeat failed: %s", exc)
            time.sleep(WORKER_HEARTBEAT_INTERVAL)

    # ------------------------------------------------------------------
    # Task handling
    # ------------------------------------------------------------------

    def _listen_for_tasks(self) -> None:
        """Accept and process task dispatch connections from the master."""
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((WORKER_LISTEN_HOST, self.worker_port))
        self._server_sock.listen(8)
        logger.info("Worker %s listening on port %d", self.node_id, self.worker_port)

        while self._running:
            try:
                client_sock, addr = self._server_sock.accept()
            except OSError:
                break
            threading.Thread(
                target=self._handle_task,
                args=(client_sock, addr),
                daemon=True,
            ).start()

    def _handle_task(self, sock: socket.socket, addr: tuple) -> None:
        """Receive one TASK_SUBMIT message, execute it, and return the result."""
        sock.settimeout(SOCKET_TIMEOUT)
        try:
            msg = recv_message(sock)
            if msg.type != MessageType.TASK_SUBMIT:
                logger.warning("Expected TASK_SUBMIT, got %s from %s", msg.type, addr)
                return

            task_id = msg.payload.get("task_id", "unknown")
            task_type = TaskType(msg.payload["task_type"])
            data = msg.payload.get("data", {})

            logger.info("Executing task %s (type=%s)", task_id, task_type)

            if task_type == TaskType.PYCUDA:
                result = self._run_pycuda_task(data)
            else:
                # LLM_INFERENCE tasks are handled directly by llama-rpc-server;
                # the coordinator uses the RPC endpoint, not this dispatch path.
                result = {"status": TaskResultStatus.RPC_OFFLOADED, "rpc_endpoint": f"{self._get_local_ip()}:{self.rpc_port}"}

            send_message(
                sock,
                Message(
                    type=MessageType.TASK_RESULT,
                    payload={"task_id": task_id, "result": result},
                ),
            )
        except Exception as exc:
            logger.exception("Task execution failed: %s", exc)
            try:
                send_message(
                    sock,
                    Message(
                        type=MessageType.TASK_ERROR,
                        payload={"error": str(exc)},
                    ),
                )
            except Exception:
                pass
        finally:
            sock.close()

    def _run_pycuda_task(self, data: dict) -> dict:
        """Execute a PyCUDA workload and return the encoded result."""
        if self._pycuda_worker is None:
            raise RuntimeError("PyCUDA is not available on this node")
        return self._pycuda_worker.execute(data)

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _get_local_ip(self) -> str:
        """Return the local IP address of the network interface facing the master."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((self.master_host, self.master_port))
                return s.getsockname()[0]
        except Exception:
            return socket.gethostbyname(socket.gethostname())

    def _signal_handler(self, signum: int, frame: Optional[types.FrameType]) -> None:
        logger.info("Received signal %d, shutting down", signum)
        self.stop()


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="Jetson Nano cluster worker")
    parser.add_argument(
        "--master-host",
        default=os.environ.get("MASTER_HOST", MASTER_CONNECT_DEFAULT),
        help="Master coordinator IP/hostname",
    )
    parser.add_argument(
        "--master-port",
        type=int,
        default=int(os.environ.get("MASTER_PORT", str(MASTER_PORT))),
        help="Master coordinator TCP port",
    )
    parser.add_argument(
        "--node-id",
        default=os.environ.get("NODE_ID"),
        help="Unique node identifier (auto-generated if not specified)",
    )
    parser.add_argument("--worker-port", type=int, default=WORKER_PORT)
    parser.add_argument("--rpc-port", type=int, default=LLAMACPP_RPC_PORT)
    parser.add_argument("--pycuda-port", type=int, default=PYCUDA_TASK_PORT)
    args = parser.parse_args()

    worker = Worker(
        master_host=args.master_host,
        master_port=args.master_port,
        node_id=args.node_id,
        worker_port=args.worker_port,
        rpc_port=args.rpc_port,
        pycuda_port=args.pycuda_port,
    )
    worker.start()


if __name__ == "__main__":
    main()
