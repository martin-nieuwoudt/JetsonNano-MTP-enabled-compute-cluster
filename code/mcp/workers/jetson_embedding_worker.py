#!/usr/bin/env python3
"""
jetson_embedding_worker.py — Tier 1 embedding worker (star topology, port 9998).
Runs on each Jetson Nano. Maps token-id shards to float16 embedding vectors via a
projection kernel (token_id -> row of a static weight matrix). Throttling is handled
on the PC side (asyncio.Semaphore); this worker just computes.

Protocol:
  recv 8-byte header:  struct.pack("!II", seq_id, num_tokens) + 4 padding bytes
  recv num_tokens*4 bytes int32 token ids
  compute output = weight_matrix[token_ids]  (float16, shape num_tokens x EMBEDDING_DIM)
  send 8-byte header:  struct.pack("!II", seq_id, len(out_bytes))
  send out_bytes
"""
import socket
import struct
import argparse
import numpy as np
import pycuda.autoinit
import pycuda.driver as cuda
from pycuda.compiler import SourceModule

EMBEDDING_DIM = 768
VOCAB_SIZE = 50000

mod = SourceModule("""
__global__ void projectEmbeddings(const int *token_ids, const half *weight_matrix,
                                  half *output_embeddings, int num_tokens, int embedding_dim) {
    int token_idx = blockIdx.y * blockDim.y + threadIdx.y;
    int feature_idx = blockIdx.x * blockDim.x + threadIdx.x;
    if (token_idx < num_tokens && feature_idx < embedding_dim) {
        int weight_row = token_ids[token_idx];
        output_embeddings[token_idx * embedding_dim + feature_idx] =
            weight_matrix[weight_row * embedding_dim + feature_idx];
    }
}
""")
projection_kernel = mod.get_function("projectEmbeddings")


def receive_exact(sock, num_bytes):
    data = bytearray()
    while len(data) < num_bytes:
        packet = sock.recv(num_bytes - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data


def run_worker(port=9998):
    rng = np.random.default_rng(0)
    h_weights = rng.standard_normal((VOCAB_SIZE, EMBEDDING_DIM)).astype(np.float16)
    d_weights = cuda.mem_alloc(h_weights.nbytes)
    cuda.memcpy_htod(d_weights, h_weights)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(5)
    print(f"[Jetson Embed] worker live on port {port}", flush=True)
    while True:
        conn, _addr = server.accept()
        try:
            # Doc wire format: 12-byte header = !II (seq, num_tokens) + 4 padding bytes.
            header = conn.recv(12)
            if not header or len(header) < 12:
                continue
            seq_id, num_tokens = struct.unpack("!II", header[:8])
            raw = receive_exact(conn, num_tokens * 4)
            if not raw:
                continue
            h_tokens = np.frombuffer(raw, dtype=np.int32)
            h_out = np.empty((num_tokens, EMBEDDING_DIM), dtype=np.float16)
            d_tokens = cuda.mem_alloc(h_tokens.nbytes)
            d_out = cuda.mem_alloc(h_out.nbytes)
            cuda.memcpy_htod(d_tokens, h_tokens)
            block = (16, 16, 1)
            grid = ((EMBEDDING_DIM + 15) // 16, (num_tokens + 15) // 16, 1)
            projection_kernel(d_tokens, d_weights, d_out,
                              np.int32(num_tokens), np.int32(EMBEDDING_DIM),
                              block=block, grid=grid)
            cuda.memcpy_dtoh(h_out, d_out)
            out_bytes = h_out.tobytes()
            conn.sendall(struct.pack("!II", seq_id, len(out_bytes)) + out_bytes)
        except Exception as e:  # noqa: BLE001
            print(f"[Jetson Embed Error]: {e}", flush=True)
        finally:
            conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9998)
    args = ap.parse_args()
    run_worker(port=args.port)
