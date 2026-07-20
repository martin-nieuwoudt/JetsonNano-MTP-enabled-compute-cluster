#!/usr/bin/env python3
"""
jetson_worker.py — Tier 1 GEMM worker (star topology, port 9999).
Runs on each Jetson Nano. Accepts a float16 shard over a socket, computes
A @ A^T on the Maxwell GPU via PyCUDA, streams the result back.

Protocol (per the design doc):
  recv 12-byte header: struct.pack("!III", seq_id, rows, cols) + 4 padding bytes
  recv rows*cols*2 bytes float16 payload
  compute C = A @ A^T  (float16)
  send 8-byte header:  struct.pack("!II", seq_id, len(out_bytes))
  send out_bytes (float16, shape rows x rows)
"""
import socket
import struct
import argparse
import numpy as np
import pycuda.autoinit
import pycuda.driver as cuda
from pycuda.compiler import SourceModule

# Minimalist FP16 matrix-multiply kernel for Maxwell (Compute Capability 5.3).
# Uses FP16 storage, accumulates in FP32 for stability (no Tensor Cores — legacy HW).
mod = SourceModule("""
__global__ void matMulFP16(const half *A, half *C, int rows, int cols) {
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    int col = blockIdx.x * blockDim.x + threadIdx.x;
    if (row < rows && col < rows) {
        float acc = 0.0f;
        for (int k = 0; k < cols; k++) {
            float a = __half2float(A[row * cols + k]);
            float b = __half2float(A[col * cols + k]);
            acc += a * b;
        }
        C[row * rows + col] = __float2half(acc);
    }
}
""")
mat_mul_kernel = mod.get_function("matMulFP16")


def receive_all(sock, num_bytes):
    data = bytearray()
    while len(data) < num_bytes:
        packet = sock.recv(num_bytes - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data


def run_worker(port=9999):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", port))
    server.listen(5)
    print(f"[Jetson GEMM] worker live on port {port}", flush=True)
    while True:
        conn, _addr = server.accept()
        try:
            # Doc wire format: 16-byte header = !III (seq, rows, cols) + 4 padding bytes.
            header = conn.recv(16)
            if not header or len(header) < 16:
                continue
            seq_id, rows, cols = struct.unpack("!III", header[:12])
            payload = receive_all(conn, rows * cols * 2)
            if not payload:
                continue
            h_a = np.frombuffer(payload, dtype=np.float16).reshape(rows, cols)
            d_a = cuda.mem_alloc(h_a.nbytes)
            d_c = cuda.mem_alloc(rows * rows * 2)
            cuda.memcpy_htod(d_a, h_a)
            block = (16, 16, 1)
            grid = ((rows + 15) // 16, (rows + 15) // 16, 1)
            mat_mul_kernel(d_a, d_c, np.int32(rows), np.int32(cols),
                           block=block, grid=grid)
            h_c = np.empty((rows, rows), dtype=np.float16)
            cuda.memcpy_dtoh(h_c, d_c)
            out_bytes = h_c.tobytes()
            conn.sendall(struct.pack("!II", seq_id, len(out_bytes)) + out_bytes)
        except Exception as e:  # noqa: BLE001
            print(f"[Jetson GEMM Error]: {e}", flush=True)
        finally:
            conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9999)
    args = ap.parse_args()
    run_worker(port=args.port)
