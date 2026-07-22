"""
Tests for master.pycuda_distributor — payload encoding/decoding and dispatch.
"""

from __future__ import annotations

import base64
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from master.pycuda_distributor import PyCUDADistributor, _encode_array
from shared.protocol import TaskType


class TestEncodeArray(unittest.TestCase):
    def test_roundtrip(self):
        arr = np.array([1.0, 2.0, 3.0], dtype=np.float32)
        encoded = _encode_array(arr)
        self.assertEqual(encoded["dtype"], "float32")
        self.assertEqual(encoded["shape"], [3])
        recovered = np.frombuffer(base64.b64decode(encoded["data"]), dtype=np.float32)
        np.testing.assert_array_equal(recovered, arr)

    def test_int32(self):
        arr = np.array([10, 20], dtype=np.int32)
        encoded = _encode_array(arr)
        self.assertEqual(encoded["dtype"], "int32")
        recovered = np.frombuffer(base64.b64decode(encoded["data"]), dtype=np.int32)
        np.testing.assert_array_equal(recovered, arr)


class TestBuildPayload(unittest.TestCase):
    def test_payload_structure(self):
        kernel = "__global__ void add(float *a, float *b, float *c){}"
        a = np.ones(4, dtype=np.float32)
        b = np.ones(4, dtype=np.float32) * 2
        payload = PyCUDADistributor._build_payload(
            kernel_source=kernel,
            kernel_name="add",
            inputs=[a, b],
            output_shape=[4],
            output_dtype="float32",
            grid=(1, 1, 1),
            block=(4, 1, 1),
        )
        self.assertEqual(payload["kernel_name"], "add")
        self.assertEqual(payload["output_shape"], [4])
        self.assertEqual(payload["output_dtype"], "float32")
        self.assertEqual(payload["grid"], [1, 1, 1])
        self.assertEqual(payload["block"], [4, 1, 1])
        self.assertEqual(len(payload["inputs"]), 2)


class TestDecodeResult(unittest.TestCase):
    def test_valid_result(self):
        arr = np.array([3.0, 3.0, 3.0, 3.0], dtype=np.float32)
        result = {
            "dtype": "float32",
            "shape": [4],
            "data": base64.b64encode(arr.tobytes()).decode("ascii"),
        }
        decoded = PyCUDADistributor._decode_result(result)
        np.testing.assert_array_almost_equal(decoded, arr)

    def test_invalid_result_returns_none(self):
        result = {"dtype": "float32", "shape": [4], "data": "!!!not_base64!!!"}
        decoded = PyCUDADistributor._decode_result(result)
        self.assertIsNone(decoded)


class TestPyCUDADistributorDispatch(unittest.TestCase):
    def _make_distributor_with_mock_coord(self, result_payload):
        coordinator = MagicMock()
        coordinator.submit_task.return_value = result_payload
        return PyCUDADistributor(coordinator)

    def test_dispatch_returns_numpy_array(self):
        arr = np.array([3.0] * 4, dtype=np.float32)
        result_payload = {
            "dtype": "float32",
            "shape": [4],
            "data": base64.b64encode(arr.tobytes()).decode("ascii"),
        }
        dist = self._make_distributor_with_mock_coord(result_payload)
        output = dist.dispatch(
            kernel_source="__global__ void k(){}",
            kernel_name="k",
            inputs=[np.ones(4, np.float32), np.ones(4, np.float32) * 2],
            output_shape=[4],
            output_dtype="float32",
        )
        np.testing.assert_array_almost_equal(output, arr)

    def test_dispatch_returns_none_on_timeout(self):
        dist = self._make_distributor_with_mock_coord(None)
        result = dist.dispatch(
            kernel_source="__global__ void k(){}",
            kernel_name="k",
            inputs=[],
            output_shape=[1],
        )
        self.assertIsNone(result)

    def test_submit_task_called_with_pycuda_type(self):
        coordinator = MagicMock()
        coordinator.submit_task.return_value = None
        dist = PyCUDADistributor(coordinator)
        dist.dispatch(
            kernel_source="k",
            kernel_name="k",
            inputs=[],
            output_shape=[1],
        )
        call_kwargs = coordinator.submit_task.call_args
        self.assertEqual(call_kwargs[1]["task_type"], TaskType.PYCUDA)


if __name__ == "__main__":
    unittest.main()
