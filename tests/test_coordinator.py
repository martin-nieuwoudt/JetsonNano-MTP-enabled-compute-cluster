"""
Tests for master.coordinator — node registry, heartbeat watchdog, task dispatch.
"""

from __future__ import annotations

import socket
import threading
import time
import unittest

from master.coordinator import Coordinator, NodeRecord
from shared.config import MASTER_PORT
from shared.protocol import (
    Message,
    MessageType,
    NodeStatus,
    TaskType,
    recv_message,
    send_message,
)


def _free_port() -> int:
    """Return an available local TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestNodeRecord(unittest.TestCase):
    def test_rpc_endpoint(self):
        record = NodeRecord(
            node_id="nano-01",
            host="192.168.1.101",
            worker_port=7010,
            rpc_port=50052,
            pycuda_port=7020,
        )
        self.assertEqual(record.rpc_endpoint, "192.168.1.101:50052")

    def test_default_status_is_online(self):
        record = NodeRecord(
            node_id="x", host="h", worker_port=1, rpc_port=2, pycuda_port=3
        )
        self.assertEqual(record.status, NodeStatus.ONLINE)


class TestCoordinatorRegistration(unittest.TestCase):
    """Test register / heartbeat / deregister flows against a live coordinator."""

    def setUp(self):
        self.port = _free_port()
        self.coordinator = Coordinator(host="127.0.0.1", port=self.port)
        self._thread = threading.Thread(target=self.coordinator.start, daemon=True)
        self._thread.start()
        time.sleep(0.1)  # Give the server a moment to bind

    def tearDown(self):
        self.coordinator.stop()

    def _connect(self):
        sock = socket.create_connection(("127.0.0.1", self.port), timeout=5)
        sock.settimeout(5)
        return sock

    def _register(self, node_id: str = "test-node", worker_port: int = 7010):
        sock = self._connect()
        send_message(
            sock,
            Message(
                type=MessageType.REGISTER,
                payload={
                    "node_id": node_id,
                    "host": "127.0.0.1",
                    "worker_port": worker_port,
                    "rpc_port": 50052,
                    "pycuda_port": 7020,
                },
            ),
        )
        ack = recv_message(sock)
        sock.close()
        return ack

    def test_register_returns_ack(self):
        ack = self._register("nano-01")
        self.assertEqual(ack.type, MessageType.REGISTER_ACK)
        self.assertEqual(ack.payload["status"], "ok")

    def test_registered_node_appears_in_online_nodes(self):
        self._register("nano-02")
        time.sleep(0.05)
        ids = [n.node_id for n in self.coordinator.online_nodes()]
        self.assertIn("nano-02", ids)

    def test_heartbeat_updates_timestamp(self):
        self._register("nano-hb")
        time.sleep(0.05)

        with self.coordinator._nodes_lock:
            before = self.coordinator._nodes["nano-hb"].last_heartbeat

        sock = self._connect()
        send_message(
            sock,
            Message(type=MessageType.HEARTBEAT, payload={"node_id": "nano-hb"}),
        )
        recv_message(sock)
        sock.close()

        with self.coordinator._nodes_lock:
            after = self.coordinator._nodes["nano-hb"].last_heartbeat

        self.assertGreaterEqual(after, before)

    def test_deregister_marks_node_offline(self):
        self._register("nano-bye")
        time.sleep(0.05)

        sock = self._connect()
        send_message(
            sock,
            Message(type=MessageType.DEREGISTER, payload={"node_id": "nano-bye"}),
        )
        sock.close()
        time.sleep(0.05)

        with self.coordinator._nodes_lock:
            self.assertEqual(
                self.coordinator._nodes["nano-bye"].status, NodeStatus.OFFLINE
            )

    def test_node_list_response(self):
        self._register("nano-list")
        time.sleep(0.05)

        sock = self._connect()
        send_message(sock, Message(type=MessageType.NODE_LIST))
        resp = recv_message(sock)
        sock.close()

        self.assertEqual(resp.type, MessageType.NODE_LIST)
        node_ids = [n["node_id"] for n in resp.payload["nodes"]]
        self.assertIn("nano-list", node_ids)

    def test_heartbeat_watchdog_marks_stale_nodes_offline(self):
        """Nodes that miss heartbeats are marked offline by the watchdog."""
        self._register("nano-stale")
        time.sleep(0.05)

        # Manually set last_heartbeat far in the past
        with self.coordinator._nodes_lock:
            self.coordinator._nodes["nano-stale"].last_heartbeat -= 100

        # Wait for the watchdog to run
        time.sleep(2)

        with self.coordinator._nodes_lock:
            self.assertEqual(
                self.coordinator._nodes["nano-stale"].status, NodeStatus.OFFLINE
            )

    def test_rpc_endpoints_returns_strings(self):
        self._register("nano-rpc")
        time.sleep(0.05)
        endpoints = self.coordinator.rpc_endpoints()
        self.assertTrue(any("50052" in ep for ep in endpoints))


class TestCoordinatorTaskDispatch(unittest.TestCase):
    """Test end-to-end task submission through the coordinator."""

    def setUp(self):
        self.coord_port = _free_port()
        self.worker_port = _free_port()
        self.coordinator = Coordinator(host="127.0.0.1", port=self.coord_port)
        threading.Thread(target=self.coordinator.start, daemon=True).start()
        time.sleep(0.1)

        # Start a mock worker that accepts one TASK_SUBMIT and echoes a result
        self._mock_worker_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._mock_worker_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._mock_worker_sock.bind(("127.0.0.1", self.worker_port))
        self._mock_worker_sock.listen(4)
        threading.Thread(target=self._mock_worker_loop, daemon=True).start()

        # Register the mock worker with the coordinator
        reg_sock = socket.create_connection(("127.0.0.1", self.coord_port), timeout=5)
        send_message(
            reg_sock,
            Message(
                type=MessageType.REGISTER,
                payload={
                    "node_id": "mock-worker",
                    "host": "127.0.0.1",
                    "worker_port": self.worker_port,
                    "rpc_port": 50052,
                    "pycuda_port": 7020,
                },
            ),
        )
        recv_message(reg_sock)
        reg_sock.close()
        time.sleep(0.05)

    def _mock_worker_loop(self):
        while True:
            try:
                conn, _ = self._mock_worker_sock.accept()
            except OSError:
                break
            conn.settimeout(5)
            msg = recv_message(conn)
            task_id = msg.payload.get("task_id", "")
            send_message(
                conn,
                Message(
                    type=MessageType.TASK_RESULT,
                    payload={"task_id": task_id, "result": {"answer": 42}},
                ),
            )
            conn.close()

    def tearDown(self):
        self.coordinator.stop()
        self._mock_worker_sock.close()

    def test_submit_task_returns_result(self):
        result = self.coordinator.submit_task(
            task_type=TaskType.PYCUDA,
            payload={"kernel_source": "dummy"},
            timeout=5,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["answer"], 42)

    def test_submit_task_no_nodes_raises(self):
        coordinator = Coordinator(host="127.0.0.1", port=_free_port())
        with self.assertRaises(RuntimeError):
            coordinator.submit_task(
                task_type=TaskType.PYCUDA, payload={}, timeout=1
            )


if __name__ == "__main__":
    unittest.main()
