"""
LLM inference distributor for the Jetson Nano compute cluster.

This module wraps **llama.cpp**'s RPC backend to distribute inference across
multiple Jetson Nano nodes.  The llama.cpp binary on the *master* PC connects
to the ``llama-rpc-server`` processes already running on the Nano nodes (see
``worker/llm_rpc_server.py``).

Typical usage::

    from master.coordinator import Coordinator
    from master.llm_distributor import LLMDistributor

    coordinator = Coordinator()
    distributor = LLMDistributor(coordinator)

    result = distributor.infer(
        model_path="models/llama-3.1-8B-Q4_K_M.gguf",
        prompt="Explain unified memory in Jetson Nano.",
        max_tokens=256,
    )
    print(result["text"])

llama.cpp RPC flag
------------------
When more than one node is available, the ``--rpc`` argument is set to a
comma-separated list of ``host:port`` strings, e.g.::

    --rpc 192.168.1.101:50052,192.168.1.102:50052,...

The local master PC is *CPU-only*.  The ``-ngl`` flag is set to
:data:`~shared.config.N_GPU_LAYERS_ALL` (``99``), which tells llama.cpp to
offload that many transformer layers to GPU via the RPC endpoints.  Because
the master has no local GPU, all layers are routed to the Jetson Nano nodes
over the RPC connection — effectively offloading *all* GPU computation to the
Nano cluster.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from master.coordinator import Coordinator

from shared.config import LLAMACPP_BINARY, N_GPU_LAYERS_ALL

logger = logging.getLogger(__name__)

# Local llama.cpp CLI binary name (master side only runs CPU inference logic)
LLAMACPP_CLI_BINARY = "llama-cli"


class LLMDistributor:
    """
    Distribute LLM inference across all online Jetson Nano nodes via
    llama.cpp's RPC backend.

    Parameters
    ----------
    coordinator:
        The :class:`~master.coordinator.Coordinator` instance that tracks
        live worker nodes.
    llama_cli_path:
        Absolute path to the ``llama-cli`` (or ``main``) binary on the
        Master PC.  Defaults to the binary found on ``PATH``.
    """

    def __init__(
        self,
        coordinator: "Coordinator",
        llama_cli_path: Optional[str] = None,
    ) -> None:
        self.coordinator = coordinator
        self._llama_cli = llama_cli_path or shutil.which(LLAMACPP_CLI_BINARY) or LLAMACPP_CLI_BINARY

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def build_rpc_flag(self, nodes: Optional[List] = None) -> str:
        """
        Build the comma-separated ``--rpc`` value for llama.cpp.

        Parameters
        ----------
        nodes:
            Optional explicit list of :class:`~master.coordinator.NodeRecord`
            objects.  Defaults to all online nodes reported by the coordinator.

        Returns
        -------
        str
            A comma-separated ``host:port`` string, e.g.
            ``"192.168.1.101:50052,192.168.1.102:50052"``.

        Raises
        ------
        RuntimeError
            If no online nodes are available.
        """
        if nodes is None:
            nodes = self.coordinator.online_nodes()
        if not nodes:
            raise RuntimeError("No online Jetson Nano nodes available for RPC inference")
        return ",".join(n.rpc_endpoint for n in nodes)

    def build_command(
        self,
        model_path: str,
        prompt: str,
        *,
        max_tokens: int = 128,
        temperature: float = 0.8,
        context_size: int = 2048,
        extra_args: Optional[List[str]] = None,
    ) -> List[str]:
        """
        Construct the full ``llama-cli`` command list.

        The master PC passes ``-ngl 0`` so *no* layers are computed locally
        — all matrix multiplications are offloaded to the Nano GPUs via RPC.

        Parameters
        ----------
        model_path:
            Path to the GGUF model file accessible from the master.
        prompt:
            The user prompt string.
        max_tokens:
            Maximum number of new tokens to generate.
        temperature:
            Sampling temperature.
        context_size:
            KV-cache context window size.
        extra_args:
            Additional raw arguments appended verbatim.

        Returns
        -------
        list[str]
            The argv list suitable for :func:`subprocess.run`.
        """
        rpc_endpoints = self.build_rpc_flag()
        cmd = [
            self._llama_cli,
            "--model", model_path,
            "--rpc", rpc_endpoints,
            "-ngl", str(N_GPU_LAYERS_ALL),  # offload all layers to RPC (Nano GPUs)
            "--n-predict", str(max_tokens),
            "--ctx-size", str(context_size),
            "--temp", str(temperature),
            "--prompt", prompt,
            "--no-display-prompt",  # suppress echoed prompt in output
        ]
        if extra_args:
            cmd.extend(extra_args)
        return cmd

    def infer(
        self,
        model_path: str,
        prompt: str,
        *,
        max_tokens: int = 128,
        temperature: float = 0.8,
        context_size: int = 2048,
        extra_args: Optional[List[str]] = None,
        timeout: Optional[float] = None,
    ) -> dict:
        """
        Run LLM inference synchronously and return the result.

        Parameters
        ----------
        model_path:
            Path to the GGUF model file.
        prompt:
            User prompt.
        max_tokens:
            Maximum tokens to generate.
        temperature:
            Sampling temperature.
        context_size:
            KV-cache context size.
        extra_args:
            Additional raw arguments for ``llama-cli``.
        timeout:
            Optional timeout in seconds for the subprocess.

        Returns
        -------
        dict
            ``{"text": <generated text>, "returncode": <int>}``

        Raises
        ------
        FileNotFoundError
            If the ``llama-cli`` binary is not found.
        subprocess.TimeoutExpired
            If inference exceeds *timeout* seconds.
        """
        model_path = str(Path(model_path).resolve())
        cmd = self.build_command(
            model_path,
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            context_size=context_size,
            extra_args=extra_args,
        )
        logger.info("Running LLM inference: %s", " ".join(cmd[:6]) + " ...")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            logger.error("llama-cli stderr: %s", result.stderr)

        return {
            "text": result.stdout.strip(),
            "returncode": result.returncode,
        }
