"""
llama.cpp RPC server manager for Jetson Nano worker nodes.

Each Jetson Nano runs one instance of ``llama-rpc-server``.  This module
provides a :class:`LLMRPCServer` class that manages the subprocess lifecycle:
start, health-check, and graceful shutdown.

The server listens on :data:`~shared.config.LLAMACPP_RPC_PORT` and accepts
connections from the Windows Master PC's ``llama-cli`` process (see
:mod:`master.llm_distributor`).

Usage::

    from worker.llm_rpc_server import LLMRPCServer

    server = LLMRPCServer(host="0.0.0.0", port=50052)
    server.start()
    # ... keep running until shutdown signal ...
    server.stop()

llama.cpp memory notes (UMA)
-----------------------------
On the Jetson Nano, model weights loaded with ``--mlock`` are pinned in the
shared DRAM pool and are accessible by both the CPU and GPU without explicit
DMA transfers.  The ``--numa numactl`` flag is *not* used here because the
Nano has a single NUMA node.
"""

from __future__ import annotations

import logging
import os
import shutil
import signal
import subprocess
import time
from typing import Optional

from shared.config import LLAMACPP_BINARY, LLAMACPP_RPC_HOST, LLAMACPP_RPC_PORT

logger = logging.getLogger(__name__)


class LLMRPCServer:
    """
    Manage the lifecycle of a ``llama-rpc-server`` subprocess on a Jetson Nano.

    Parameters
    ----------
    host:
        IP address to bind (default ``0.0.0.0``).
    port:
        TCP port to listen on (default :data:`~shared.config.LLAMACPP_RPC_PORT`).
    binary:
        Path to the ``llama-rpc-server`` binary.  Resolved via ``PATH`` if not
        specified.
    """

    def __init__(
        self,
        host: str = LLAMACPP_RPC_HOST,
        port: int = LLAMACPP_RPC_PORT,
        binary: Optional[str] = None,
    ) -> None:
        self.host = host
        self.port = port
        self._binary = binary or shutil.which(LLAMACPP_BINARY) or LLAMACPP_BINARY
        self._process: Optional[subprocess.Popen] = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Launch the ``llama-rpc-server`` subprocess.

        Raises
        ------
        FileNotFoundError
            If the binary cannot be found.
        RuntimeError
            If the server fails to start within the startup grace period.
        """
        if self._process is not None and self._process.poll() is None:
            logger.warning("llama-rpc-server is already running (PID %d)", self._process.pid)
            return

        cmd = [
            self._binary,
            "--host", self.host,
            "--port", str(self.port),
        ]
        logger.info("Starting llama-rpc-server: %s", " ".join(cmd))

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "GGML_CUDA_ENABLE_UNIFIED_MEM": "1"},
        )

        # Brief grace period to detect immediate crash
        time.sleep(0.5)
        if self._process.poll() is not None:
            stderr = self._process.stderr.read() if self._process.stderr else ""
            raise RuntimeError(
                f"llama-rpc-server exited immediately (code {self._process.returncode}): {stderr}"
            )

        logger.info(
            "llama-rpc-server started (PID %d) on %s:%d",
            self._process.pid,
            self.host,
            self.port,
        )

    def stop(self) -> None:
        """Gracefully terminate the ``llama-rpc-server`` process."""
        if self._process is None or self._process.poll() is not None:
            return
        logger.info("Stopping llama-rpc-server (PID %d)", self._process.pid)
        self._process.send_signal(signal.SIGTERM)
        try:
            self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            logger.warning("llama-rpc-server did not stop gracefully; killing")
            self._process.kill()
        self._process = None

    def is_running(self) -> bool:
        """Return ``True`` if the subprocess is alive."""
        return self._process is not None and self._process.poll() is None

    def pid(self) -> Optional[int]:
        """Return the subprocess PID, or ``None`` if not running."""
        return self._process.pid if self._process else None

    def restart(self) -> None:
        """Stop then restart the RPC server."""
        self.stop()
        self.start()
