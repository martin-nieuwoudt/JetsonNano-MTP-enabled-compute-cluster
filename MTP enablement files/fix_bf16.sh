set -e
cd /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/vendors

# 1) create the BF16 stub shim (same as stable fleet tree) PLUS conversion intrinsics PLUS nv_bfloat162 PLUS pdl_sync
cat > cuda_bf16.h <<'EOF'
#pragma once
// Minimal bfloat16 shim for CUDA < 11.0 (Jetson Nano, CUDA 10.2).
// The type is a stub: it stores the raw bits but converts to/from float as 0.0f.
// Sufficient for the ggml-cuda build to compile on Maxwell SM 5.3; actual BF16
// compute is not exercised on this hardware path.
struct __nv_bfloat16 {
    unsigned short __x;
    __host__ __device__ __nv_bfloat16() : __x(0) {}
    __host__ __device__ __nv_bfloat16(float f) : __x(0) { (void)f; }
    __host__ __device__ operator float() const { return 0.0f; }
};
typedef __nv_bfloat16 nv_bfloat16;

// Vector type nv_bfloat162 (two nv_bfloat16) — needed for template specializations
// in mma.cuh that are guarded by TURING/AMPERE/VOLTA arch checks (never hit on SM 5.3).
struct __nv_bfloat162 {
    __nv_bfloat16 x, y;
    __host__ __device__ __nv_bfloat162() : x(), y() {}
    __host__ __device__ __nv_bfloat162(float f) : x(f), y(f) {}
    __host__ __device__ __nv_bfloat162(__nv_bfloat16 a, __nv_bfloat16 b) : x(a), y(b) {}
};
typedef __nv_bfloat162 nv_bfloat162;

// Conversion intrinsics (CUDA 11+ builtins) — stubbed for CUDA 10.2.
__host__ __device__ inline __nv_bfloat16 __float2bfloat16(float f) { return __nv_bfloat16(f); }
__host__ __device__ inline float __bfloat162float(__nv_bfloat16 x) { return (float)x; }

// Warp synchronization primitive used in fwht.cu and gated_delta_net.cu
// before __shfl_xor_sync operations. Device-only because __syncwarp() is device-only.
__device__ inline void ggml_cuda_pdl_sync() { __syncwarp(); }
EOF
echo "created cuda_bf16.h"

# 2) wire it into cuda.h: include shim when CUDA < 11.0
cd /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda
python3 - <<'PY'
p = 'vendors/cuda.h'
s = open(p).read()
old = "#if CUDART_VERSION >= 11000\n#include <cuda_bf16.h>\n#endif"
new = "#if CUDART_VERSION >= 11000\n#include <cuda_bf16.h>\n#else\n#include \"cuda_bf16.h\"\n#endif"
assert old in s, "anchor not found in cuda.h"
s = s.replace(old, new)
open(p,'w').write(s)
print("patched cuda.h")
PY

echo "=== verify ==="
grep -n "cuda_bf16" vendors/cuda.h
ls -la vendors/cuda_bf16.h
