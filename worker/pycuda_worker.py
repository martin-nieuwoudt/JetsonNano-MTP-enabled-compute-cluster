"""
PyCUDA task executor for Jetson Nano worker nodes.

Receives a serialised CUDA workload from the master coordinator, compiles the
kernel on the Nano's GPU using PyCUDA's runtime compiler, executes it, and
returns the encoded result.

Unified Memory Architecture (UMA) notes
----------------------------------------
The Jetson Nano's CPU and GPU share the same physical DRAM.  To maximise
throughput the executor uses :func:`~worker.uma_utils.alloc_pinned` and
:func:`~worker.uma_utils.numpy_to_device` from :mod:`worker.uma_utils`, which
map host buffers directly into the GPU address space without any DMA copy.

Protocol
--------
Input and output arrays are transmitted as base-64-encoded little-endian bytes
together with shape and dtype metadata (see :mod:`master.pycuda_distributor`
for the sender side).
"""

from __future__ import annotations

import base64
import logging
from typing import Any, Dict, List, Tuple

import numpy as np

from worker.uma_utils import numpy_to_device, device_to_numpy

logger = logging.getLogger(__name__)


class PyCUDAWorker:
    """
    Execute PyCUDA workloads on the Jetson Nano GPU.

    The CUDA context is initialised once during construction and reused for all
    subsequent kernel launches, avoiding expensive context-creation overhead.
    """

    def __init__(self) -> None:
        self._ctx = None
        self._init_cuda()

    def _init_cuda(self) -> None:
        """Initialise the PyCUDA driver and create a CUDA context."""
        try:
            import pycuda.driver as cuda  # noqa: PLC0415
            import pycuda.autoinit  # noqa: PLC0415, F401

            self._ctx = cuda.Context.get_current()
            device = cuda.Device(0)
            logger.info(
                "PyCUDA initialised on device: %s (compute %d.%d)",
                device.name(),
                *device.compute_capability(),
            )
        except ImportError as exc:
            raise RuntimeError(
                "PyCUDA is not installed. Install it on the Jetson Nano with: "
                "pip install pycuda"
            ) from exc

    def execute(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compile and execute a CUDA kernel described by *payload*.

        Parameters
        ----------
        payload:
            Dict with keys ``kernel_source``, ``kernel_name``, ``inputs``,
            ``output_shape``, ``output_dtype``, ``grid``, ``block`` — matching
            the schema documented in :mod:`master.pycuda_distributor`.

        Returns
        -------
        dict
            ``{"dtype": str, "shape": list, "data": base64_str}``
        """
        import pycuda.compiler as compiler  # noqa: PLC0415
        import pycuda.driver as cuda  # noqa: PLC0415

        kernel_source: str = payload["kernel_source"]
        kernel_name: str = payload["kernel_name"]
        raw_inputs: List[dict] = payload["inputs"]
        output_shape: Tuple[int, ...] = tuple(payload["output_shape"])
        output_dtype = np.dtype(payload["output_dtype"])
        grid: Tuple[int, int, int] = tuple(payload["grid"])
        block: Tuple[int, int, int] = tuple(payload["block"])

        # Decode input arrays and upload to device
        device_inputs = []
        host_inputs = []
        for inp in raw_inputs:
            dtype = np.dtype(inp["dtype"])
            shape = tuple(inp["shape"])
            data = base64.b64decode(inp["data"])
            host_arr = np.frombuffer(data, dtype=dtype).reshape(shape).copy()
            host_inputs.append(host_arr)
            device_inputs.append(numpy_to_device(host_arr))

        # Allocate output buffer (UMA: host and GPU share this memory)
        d_output = cuda.mem_alloc(int(np.prod(output_shape)) * output_dtype.itemsize)

        # Compile kernel
        module = compiler.SourceModule(kernel_source)
        kernel_fn = module.get_function(kernel_name)

        # Launch kernel
        args = device_inputs + [d_output]
        kernel_fn(*args, grid=grid, block=block)

        # Synchronise and retrieve result (zero-copy on UMA)
        cuda.Context.synchronize()
        result_arr = device_to_numpy(d_output, output_shape, output_dtype)

        return {
            "dtype": str(result_arr.dtype),
            "shape": list(result_arr.shape),
            "data": base64.b64encode(result_arr.tobytes()).decode("ascii"),
        }
