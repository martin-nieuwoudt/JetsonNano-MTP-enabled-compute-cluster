#pragma once
#include "common.cuh"

#define CUDA_DEQUANTIZE_BLOCK_SIZE 256

template<typename T>
using to_t_cuda_t = void (*)(const void * x, T * y, int64_t k, cudaStream_t stream);

typedef to_t_cuda_t<float> to_fp32_cuda_t;
typedef to_t_cuda_t<half> to_fp16_cuda_t;
typedef to_t_cuda_t<nv_bfloat16> to_bf16_cuda_t;

to_fp16_cuda_t ggml_get_to_fp16_cuda(ggml_type type);

to_bf16_cuda_t ggml_get_to_bf16_cuda(ggml_type type);

to_fp32_cuda_t ggml_get_to_fp32_cuda(ggml_type type);

// TODO more general support for non-contiguous inputs

template<typename T>
using to_t_nc_cuda_t = void (*)(const void * x, T * y,
    int64_t ne00, int64_t ne01, int64_t ne02, int64_t ne03,
    int64_t s01, int64_t s02, int64_t s03, cudaStream_t stream);

typedef to_t_nc_cuda_t<float> to_fp32_nc_cuda_t;
typedef to_t_nc_cuda_t<half> to_fp16_nc_cuda_t;
typedef to_t_nc_cuda_t<nv_bfloat16> to_bf16_nc_cuda_t;

to_fp32_nc_cuda_t ggml_get_to_fp32_nc_cuda(ggml_type type);
to_fp16_nc_cuda_t ggml_get_to_fp16_nc_cuda(ggml_type type);
to_bf16_nc_cuda_t ggml_get_to_bf16_nc_cuda(ggml_type type);

// C++14 compatible cast using overloads
template<typename dst_t, typename src_t>
__host__ __device__ inline dst_t ggml_cuda_cast(src_t x) {
    return (dst_t)((float)x);
}

// Specializations
template<> __host__ __device__ inline float ggml_cuda_cast<float, float>(float x) { return x; }
template<> __host__ __device__ inline half ggml_cuda_cast<half, half>(half x) { return x; }
template<> __host__ __device__ inline float ggml_cuda_cast<float, half>(half x) { return __half2float(x); }
template<> __host__ __device__ inline half ggml_cuda_cast<half, float>(float x) { return __float2half(x); }
template<> __host__ __device__ inline half2 ggml_cuda_cast<half2, float2>(float2 x) { return __float22half2_rn(x); }
template<> __host__ __device__ inline nv_bfloat16 ggml_cuda_cast<nv_bfloat16, float>(float x) { return __float2bfloat16(x); }
template<> __host__ __device__ inline float ggml_cuda_cast<float, nv_bfloat16>(nv_bfloat16 x) { return __bfloat162float(x); }
template<> __host__ __device__ inline int32_t ggml_cuda_cast<int32_t, float>(float x) { return (int32_t)x; }
