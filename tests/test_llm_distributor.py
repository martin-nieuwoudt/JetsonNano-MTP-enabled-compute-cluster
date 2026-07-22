"""
Tests for master.llm_distributor — command-building logic (no llama.cpp binary needed).
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from master.coordinator import NodeRecord
from master.llm_distributor import LLMDistributor
from shared.protocol import NodeStatus


def _make_node(node_id: str, host: str, rpc_port: int = 50052) -> NodeRecord:
    return NodeRecord(
        node_id=node_id,
        host=host,
        worker_port=7010,
        rpc_port=rpc_port,
        pycuda_port=7020,
        status=NodeStatus.ONLINE,
    )


class TestLLMDistributorBuildRPCFlag(unittest.TestCase):
    def _make_distributor(self, nodes):
        coordinator = MagicMock()
        coordinator.online_nodes.return_value = nodes
        return LLMDistributor(coordinator, llama_cli_path="llama-cli")

    def test_single_node(self):
        dist = self._make_distributor([_make_node("nano-01", "192.168.1.101")])
        flag = dist.build_rpc_flag()
        self.assertEqual(flag, "192.168.1.101:50052")

    def test_multiple_nodes(self):
        nodes = [
            _make_node("nano-01", "192.168.1.101", 50052),
            _make_node("nano-02", "192.168.1.102", 50052),
            _make_node("nano-03", "192.168.1.103", 50053),
        ]
        dist = self._make_distributor(nodes)
        flag = dist.build_rpc_flag()
        self.assertIn("192.168.1.101:50052", flag)
        self.assertIn("192.168.1.102:50052", flag)
        self.assertIn("192.168.1.103:50053", flag)
        # All endpoints joined by comma
        parts = flag.split(",")
        self.assertEqual(len(parts), 3)

    def test_no_nodes_raises(self):
        dist = self._make_distributor([])
        with self.assertRaises(RuntimeError):
            dist.build_rpc_flag()

    def test_explicit_nodes_override(self):
        coordinator = MagicMock()
        coordinator.online_nodes.return_value = []
        dist = LLMDistributor(coordinator, llama_cli_path="llama-cli")
        explicit = [_make_node("nano-xx", "10.0.0.1", 50052)]
        flag = dist.build_rpc_flag(nodes=explicit)
        self.assertEqual(flag, "10.0.0.1:50052")


class TestLLMDistributorBuildCommand(unittest.TestCase):
    def _make_distributor(self):
        coordinator = MagicMock()
        coordinator.online_nodes.return_value = [_make_node("nano-01", "192.168.1.101")]
        return LLMDistributor(coordinator, llama_cli_path="/usr/bin/llama-cli")

    def test_command_contains_required_flags(self):
        dist = self._make_distributor()
        cmd = dist.build_command(
            model_path="/models/test.gguf",
            prompt="Hello",
            max_tokens=64,
        )
        cmd_str = " ".join(cmd)
        self.assertIn("--model", cmd_str)
        self.assertIn("--rpc", cmd_str)
        self.assertIn("-ngl", cmd_str)
        self.assertIn("--n-predict", cmd_str)
        self.assertIn("64", cmd_str)
        self.assertIn("Hello", cmd_str)

    def test_ngl_is_99(self):
        """All GPU layers must be offloaded to RPC."""
        dist = self._make_distributor()
        cmd = dist.build_command("/m/model.gguf", "test")
        ngl_idx = cmd.index("-ngl")
        self.assertEqual(cmd[ngl_idx + 1], "99")

    def test_extra_args_appended(self):
        dist = self._make_distributor()
        cmd = dist.build_command("/m/model.gguf", "test", extra_args=["--verbose"])
        self.assertIn("--verbose", cmd)

    def test_temperature_and_context_flags(self):
        dist = self._make_distributor()
        cmd = dist.build_command(
            "/m/model.gguf", "test", temperature=0.5, context_size=1024
        )
        cmd_str = " ".join(cmd)
        self.assertIn("0.5", cmd_str)
        self.assertIn("1024", cmd_str)


class TestLLMDistributorInfer(unittest.TestCase):
    def test_infer_returns_text_on_success(self):
        coordinator = MagicMock()
        coordinator.online_nodes.return_value = [_make_node("nano-01", "192.168.1.101")]
        dist = LLMDistributor(coordinator, llama_cli_path="llama-cli")

        mock_result = MagicMock()
        mock_result.stdout = "  Hello world  "
        mock_result.stderr = ""
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = dist.infer("/models/model.gguf", "Say hello")

        self.assertEqual(result["text"], "Hello world")
        self.assertEqual(result["returncode"], 0)


if __name__ == "__main__":
    unittest.main()
