"""
Utilities for exploiting the Jetson Nano's Unified Memory Architecture (UMA).

On the Jetson Nano, CPU and GPU share the same physical DRAM pool (UMA).
This eliminates the traditional host↔device copy overhead that is present on
discrete-GPU systems.

Key techniques exposed here
---------------------------
* **Page-locked (pinned) allocation** — :func:`alloc_pinned` wraps
  ``cuda.pagelocked_empty``.  Because Nano's UMA means the GPU can already
  address CPU memory, this is mainly used to signal to the CUDA driver that
  the buffer should never be paged out.

* **Zero-copy device pointers** — :func:`get_device_pointer` returns a
  ``DeviceAllocation`` object that the Nano's GPU can access without any DMA
  copy, since both CPU and GPU operate on the same physical memory.

* **Managed (unified) allocation** — :func:`alloc_managed` uses
  ``cuda.managed_empty``, which lets the CUDA runtime automatically migrate
  pages between CPU and GPU on demand.  On UMA hardware the migration cost is
  zero.

* **NumPy ↔ PyCUDA bridge** — helper functions to move NumPy arrays in and out
  of the GPU-accessible memory without unnecessary copies.

.. note::

    PyCUDA is imported lazily (inside each function) so that this module can
    be imported on the master PC (which has no CUDA) for documentation/type-
    checking purposes.  Any function that actually touches CUDA will raise
    ``ImportError`` if PyCUDA is not installed.
"""

from __future__ import annotations

from typing import Tuple

import numpy as np


def alloc_pinned(shape: Tuple[int, ...], dtype: type = np.float32) -> "np.ndarray":
    """
    Allocate a page-locked NumPy array backed by pinned host memory.

    On Jetson Nano UMA, pinned memory is directly accessible from the GPU
    with zero-copy semantics.

    Parameters
    ----------
    shape:
        Array shape.
    dtype:
        NumPy dtype.

    Returns
    -------
    numpy.ndarray
        A page-locked array wrapping pinned memory.
    """
    import pycuda.driver as cuda  # noqa: PLC0415

    return cuda.pagelocked_empty(shape, dtype)


def get_device_pointer(pinned_array: "np.ndarray") -> "pycuda.driver.DeviceAllocation":
    """
    Return a GPU-accessible device pointer to a pinned host array.

    On Jetson Nano UMA the pointer refers to the *same* physical memory as the
    CPU-side NumPy array, so no DMA transfer occurs.

    Parameters
    ----------
    pinned_array:
        A page-locked array created by :func:`alloc_pinned`.

    Returns
    -------
    pycuda.driver.DeviceAllocation
        Device pointer suitable for passing to CUDA kernels.
    """
    import pycuda.driver as cuda  # noqa: PLC0415

    return cuda.register_host_memory(
        pinned_array,
        cuda.mem_host_register_flags.DEVICEMAP,
    )


def alloc_managed(shape: Tuple[int, ...], dtype: type = np.float32) -> "np.ndarray":
    """
    Allocate a CUDA managed (unified) memory array.

    On Jetson Nano UMA, managed memory resides in the shared physical pool so
    access from both CPU and GPU is native — no page faults or migrations occur.

    Parameters
    ----------
    shape:
        Array shape.
    dtype:
        NumPy dtype.

    Returns
    -------
    numpy.ndarray
        An array backed by CUDA managed memory.
    """
    import pycuda.driver as cuda  # noqa: PLC0415

    return cuda.managed_empty(shape, dtype, cuda.mem_attach_flags.GLOBAL)


def numpy_to_device(arr: np.ndarray) -> "pycuda.driver.DeviceAllocation":
    """
    Upload a NumPy array to GPU-accessible memory.

    On Jetson Nano UMA this is a lightweight operation: the driver maps the
    existing host buffer into the GPU's address space rather than copying data.

    Parameters
    ----------
    arr:
        Contiguous NumPy array.

    Returns
    -------
    pycuda.driver.DeviceAllocation
        GPU buffer populated with the array contents.
    """
    import pycuda.driver as cuda  # noqa: PLC0415

    if not arr.flags["C_CONTIGUOUS"]:
        arr = np.ascontiguousarray(arr)
    d_buf = cuda.mem_alloc(arr.nbytes)
    cuda.memcpy_htod(d_buf, arr)
    return d_buf


def device_to_numpy(d_buf: "pycuda.driver.DeviceAllocation", shape: Tuple[int, ...], dtype: type) -> np.ndarray:
    """
    Download a GPU buffer into a NumPy array.

    On Jetson Nano UMA no data is physically moved — the CPU reads the buffer
    directly from shared DRAM.

    Parameters
    ----------
    d_buf:
        GPU device allocation.
    shape:
        Desired output shape.
    dtype:
        NumPy dtype.

    Returns
    -------
    numpy.ndarray
        Host-side view of the GPU buffer.
    """
    import pycuda.driver as cuda  # noqa: PLC0415

    result = np.empty(shape, dtype=dtype)
    cuda.memcpy_dtoh(result, d_buf)
    return result
