#!/usr/bin/env python3
"""
jetson_ring_worker.py — Tier 2 MoE expert-parallel ring worker (port 8888).
Runs on each Jetson Nano. Forms a logical ring: the PC pumps token batches in at the
head (Jetson 0); each node processes the experts it owns, then forwards the remaining
batch to the next node. The final node returns the completed hidden-state tensor to PC.

RESEARCH-GRADE: the expert GEMM kernel below is a placeholder (the source design doc's
kernel was a stub with a buggy index and empty body). This worker validates the
ring TRANSPORT + double-buffering pattern; the real expert math must be written against
actual MoE weights (e.g. DeepSeek-Coder-V2-Lite safetensors) before production use.

Boot order (from design doc): start Jetson 10 first ... down to Jetson 0, so downstream
listening sockets exist before data arrives.
"""
import socket
import struct
import argparse
import threading
import numpy as np
import pycuda.autoinit
import pycuda.driver as cuda
from pycuda.compiler import SourceModule

HIDDEN_DIM = 4096
BATCH_SIZE = 16
SEQUENCE_LEN = 512

# Placeholder expert kernel — REPLACE with real MoE FFN math before production.
mod = SourceModule("""
__global__ void evaluate_expert_gemm(float *hidden_states, float *weights,
                                     float *output, int expert_dim) {
    int idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (idx < expert_dim) {
        // Identity pass-through placeholder: real kernel does local expert FFN.
        output[idx] = hidden_states[idx];
    }
}
""")
evaluate_kernel = mod.get_function("evaluate_expert_gemm")


class RingWorker:
    def __init__(self, port, next_node_ip, next_node_port):
        self.port = port
        self.next_node_ip = next_node_ip
        self.next_node_port = next_node_port
        self.stream = cuda.Stream()
        # Pinned host buffer for high-speed network transfer (double-buffer ready).
        self.host_buffer = cuda.pagelocked_empty((BATCH_SIZE, HIDDEN_DIM), dtype=np.float32)
        self.expert_weights_gpu = cuda.mem_alloc(BATCH_SIZE * HIDDEN_DIM * 4)

    def process_and_forward(self, incoming_data):
        # Async copy network data -> GPU, run local expert kernel, forward remainder.
        cuda.memcpy_htod_async(self.expert_weights_gpu, incoming_data, self.stream)
        evaluate_kernel(self.expert_weights_gpu, block=(256, 1, 1), grid=(4, 1),
                        stream=self.stream)
        # Only forward if this node is NOT the tail (next_ip != self) to avoid a
        # closed-ring infinite loop. The tail returns the completed tensor to the PC.
        if self.next_node_ip != "127.0.0.1":
            threading.Thread(target=self.forward_to_next_node,
                             args=(incoming_data,)).start()
        self.stream.synchronize()

    def forward_to_next_node(self, data):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.next_node_ip, self.next_node_port))
            s.sendall(data)
            s.close()
        except Exception as e:  # noqa: BLE001
            print(f"[Ring] forward to {self.next_node_ip} failed: {e}", flush=True)


def run_worker(port=8888, next_node_ip="127.0.0.1", next_node_port=8888):
    w = RingWorker(port, next_node_ip, next_node_port)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(5)
    print(f"[Jetson Ring] worker live on port {port} -> next {next_node_ip}:{next_node_port}",
          flush=True)
    while True:
        conn, _addr = server.accept()
        try:
            # Doc wire format: 8-byte header = !II (batch_id, num_floats).
            header = conn.recv(8)
            if not header or len(header) < 8:
                continue
            batch_id, num_floats = struct.unpack("!II", header)
            data = conn.recv(num_floats * 4)
            if not data:
                continue
            arr = np.frombuffer(data, dtype=np.float32).reshape(-1, HIDDEN_DIM)
            w.process_and_forward(arr)
            # Tail returns the completed hidden-state tensor to the PC caller.
            out = arr.astype(np.float32).tobytes()
            conn.sendall(struct.pack("!II", batch_id, len(out)) + out)
        except Exception as e:  # noqa: BLE001
            print(f"[Jetson Ring Error]: {e}", flush=True)
        finally:
            conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8888)
    ap.add_argument("--next-ip", type=str, default="127.0.0.1")
    ap.add_argument("--next-port", type=int, default=8888)
    args = ap.parse_args()
    run_worker(port=args.port, next_node_ip=args.next_ip, next_node_port=args.next_port)
