"""
Tests for shared.protocol — message serialisation and socket I/O.
"""

from __future__ import annotations

import socket
import struct
import threading
import unittest

from shared.protocol import (
    Message,
    MessageType,
    _recv_exact,
    recv_message,
    send_message,
)


class TestMessageSerialisation(unittest.TestCase):
    """Round-trip serialisation tests for :class:`Message`."""

    def test_roundtrip_simple(self):
        msg = Message(type=MessageType.HEARTBEAT, payload={"node_id": "nano-01"})
        data = msg.to_bytes()
        # Header: 4-byte big-endian uint32
        body_len = struct.unpack(">I", data[:4])[0]
        self.assertEqual(body_len, len(data) - 4)
        restored = Message.from_bytes(data[4:])
        self.assertEqual(restored.type, MessageType.HEARTBEAT)
        self.assertEqual(restored.payload["node_id"], "nano-01")

    def test_empty_payload(self):
        msg = Message(type=MessageType.HEARTBEAT_ACK)
        restored = Message.from_bytes(msg.to_bytes()[4:])
        self.assertEqual(restored.type, MessageType.HEARTBEAT_ACK)
        self.assertEqual(restored.payload, {})

    def test_complex_payload(self):
        payload = {
            "task_id": "abc-123",
            "result": {"dtype": "float32", "shape": [4], "data": "AAAA"},
        }
        msg = Message(type=MessageType.TASK_RESULT, payload=payload)
        restored = Message.from_bytes(msg.to_bytes()[4:])
        self.assertEqual(restored.payload["task_id"], "abc-123")
        self.assertEqual(restored.payload["result"]["shape"], [4])

    def test_all_message_types_roundtrip(self):
        for mt in MessageType:
            msg = Message(type=mt, payload={"k": "v"})
            restored = Message.from_bytes(msg.to_bytes()[4:])
            self.assertEqual(restored.type, mt)


class TestSocketIO(unittest.TestCase):
    """Integration tests for send_message / recv_message over a local socket pair."""

    def _make_connected_pair(self):
        """Return (client_sock, server_sock) connected over loopback."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        port = server.getsockname()[1]

        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(("127.0.0.1", port))
        conn, _ = server.accept()
        server.close()
        return client, conn

    def test_send_recv_roundtrip(self):
        client, server = self._make_connected_pair()
        msg = Message(type=MessageType.REGISTER, payload={"node_id": "test-node"})

        def sender():
            send_message(client, msg)
            client.close()

        t = threading.Thread(target=sender, daemon=True)
        t.start()

        received = recv_message(server)
        server.close()
        t.join()

        self.assertEqual(received.type, MessageType.REGISTER)
        self.assertEqual(received.payload["node_id"], "test-node")

    def test_recv_exact_raises_on_eof(self):
        client, server = self._make_connected_pair()
        client.close()
        with self.assertRaises(ConnectionError):
            _recv_exact(server, 4)
        server.close()


if __name__ == "__main__":
    unittest.main()
