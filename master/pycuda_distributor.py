"""
PyCUDA workload distributor for the Jetson Nano compute cluster.

The master PC is *CPU-only* — it does not execute CUDA code locally.  Instead,
this module serialises a workload description (CUDA kernel source, launch
parameters, and input data encoded as base-64 bytes) and dispatches it to a
Jetson Nano worker node via the :class:`~master.coordinator.Coordinator`.

Workload schema
---------------
A PyCUDA workload is described by a Python dict with the following keys:

``kernel_source`` (str)
    The full CUDA C source string including the kernel function definition.

``kernel_name`` (str)
    The name of the ``__global__`` function to call.

``grid`` (tuple[int, int, int])
    CUDA grid dimensions ``(grid_x, grid_y, grid_z)``.

``block`` (tuple[int, int, int])
    CUDA block dimensions ``(block_x, block_y, block_z)``.

``inputs`` (list[dict])
    List of input arrays, each described as::

        {
            "dtype": "float32",            # numpy dtype string
            "shape": [N],                  # list of ints
            "data": "<base64-encoded bytes>"
        }

``output_shape`` (list[int])
    Shape of the single output array the kernel writes.

``output_dtype`` (str)
    NumPy dtype string for the output, e.g. ``"float32"``.

Example::

    import base64
    import numpy as np
    from master.coordinator import Coordinator
    from master.pycuda_distributor import PyCUDADistributor

    coordinator = Coordinator()
    dist = PyCUDADistributor(coordinator)

    kernel_source = r\"\"\"
    __global__ void vector_add(const float *a, const float *b, float *c, int n) {
        int i = blockIdx.x * blockDim.x + threadIdx.x;
        if (i < n) c[i] = a[i] + b[i];
    }
    \"\"\"

    n = 1024
    a = np.ones(n, dtype=np.float32)
    b = np.ones(n, dtype=np.float32) * 2.0

    result = dist.dispatch(
        kernel_source=kernel_source,
        kernel_name="vector_add",
        inputs=[a, b, np.array([n], dtype=np.int32)],
        output_shape=[n],
        output_dtype="float32",
        grid=(n // 256 + 1, 1, 1),
        block=(256, 1, 1),
    )
    print(result)  # ndarray of 3.0 values
"""

from __future__ import annotations

import base64
import logging
from typing import TYPE_CHECKING, List, Optional, Tuple

import numpy as np

if TYPE_CHECKING:
    from master.coordinator import Coordinator

from shared.config import TASK_TIMEOUT
from shared.protocol import TaskType

logger = logging.getLogger(__name__)


def _encode_array(arr: np.ndarray) -> dict:
    """Encode a NumPy array to a JSON-serialisable dict."""
    return {
        "dtype": str(arr.dtype),
        "shape": list(arr.shape),
        "data": base64.b64encode(arr.tobytes()).decode("ascii"),
    }


class PyCUDADistributor:
    """
    Distribute PyCUDA workloads to Jetson Nano workers.

    Parameters
    ----------
    coordinator:
        Live :class:`~master.coordinator.Coordinator` instance.
    """

    def __init__(self, coordinator: "Coordinator") -> None:
        self.coordinator = coordinator

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def dispatch(
        self,
        kernel_source: str,
        kernel_name: str,
        inputs: List[np.ndarray],
        output_shape: List[int],
        output_dtype: str = "float32",
        grid: Tuple[int, int, int] = (1, 1, 1),
        block: Tuple[int, int, int] = (256, 1, 1),
        timeout: float = TASK_TIMEOUT,
    ) -> Optional[np.ndarray]:
        """
        Dispatch a PyCUDA kernel to an available Jetson Nano node.

        Parameters
        ----------
        kernel_source:
            CUDA C source containing the ``__global__`` kernel function.
        kernel_name:
            Name of the kernel function to launch.
        inputs:
            List of NumPy arrays passed as kernel arguments (in order).
        output_shape:
            Shape of the output array written by the kernel.
        output_dtype:
            NumPy dtype of the output array.
        grid:
            CUDA grid dimensions ``(x, y, z)``.
        block:
            CUDA block dimensions ``(x, y, z)``.
        timeout:
            Seconds to wait for a result.

        Returns
        -------
        numpy.ndarray or None
            The output array decoded from the worker result, or ``None`` on
            timeout / error.
        """
        payload = self._build_payload(
            kernel_source=kernel_source,
            kernel_name=kernel_name,
            inputs=inputs,
            output_shape=output_shape,
            output_dtype=output_dtype,
            grid=grid,
            block=block,
        )

        result = self.coordinator.submit_task(
            task_type=TaskType.PYCUDA,
            payload=payload,
            timeout=timeout,
        )

        if result is None:
            logger.error("PyCUDA task timed out or failed")
            return None

        return self._decode_result(result)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_payload(
        kernel_source: str,
        kernel_name: str,
        inputs: List[np.ndarray],
        output_shape: List[int],
        output_dtype: str,
        grid: Tuple[int, int, int],
        block: Tuple[int, int, int],
    ) -> dict:
        """Serialise a PyCUDA workload into the wire-protocol payload dict."""
        return {
            "kernel_source": kernel_source,
            "kernel_name": kernel_name,
            "inputs": [_encode_array(arr) for arr in inputs],
            "output_shape": list(output_shape),
            "output_dtype": output_dtype,
            "grid": list(grid),
            "block": list(block),
        }

    @staticmethod
    def _decode_result(result: dict) -> Optional[np.ndarray]:
        """Decode the worker's result dict back to a NumPy array."""
        try:
            dtype = np.dtype(result["dtype"])
            shape = tuple(result["shape"])
            data = base64.b64decode(result["data"])
            return np.frombuffer(data, dtype=dtype).reshape(shape)
        except Exception as exc:
            logger.error("Failed to decode PyCUDA result: %s", exc)
            return None
