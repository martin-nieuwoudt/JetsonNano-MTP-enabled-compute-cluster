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

// C++14 compatible version - no if constexpr
template<typename dst_t, typename src_t>
__host__ __device__ inline dst_t ggml_cuda_cast(src_t x) {
    // Use template specialization instead of if constexpr
    return ggml_cuda_cast_impl<dst_t, src_t>(x);
}

// Helper struct for template specialization
template<typename dst_t, typename src_t, typename = void>
struct ggml_cuda_cast_helper {
    static __host__ __device__ inline dst_t cast(src_t x) {
        return float(x);
    }
};

// Specialization for same type
template<typename T>
struct ggml_cuda_cast_helper<T, T, void> {
    static __host__ __device__ inline T cast(T x) {
        return x;
    }
};

// Specialization for nv_bfloat16 destination
template<typename src_t>
struct ggml_cuda_cast_helper<nv_bfloat16, src_t, void> {
    static __host__ __device__ inline nv_bfloat16 cast(src_t x) {
        return __float2bfloat16(float(x));
    }
};

// Specialization for nv_bfloat16 source
template<typename dst_t>
struct ggml_cuda_cast_helper<dst_t, nv_bfloat16, void> {
    static __host__ __device__ inline dst_t cast(nv_bfloat16 x) {
        return __bfloat162float(x);
    }
};

// Specialization for float2 -> half2
template<>
struct ggml_cuda_cast_helper<half2, float2, void> {
    static __host__ __device__ inline half2 cast(float2 x) {
        return __float22half2_rn(x);
    }
};

// Specialization for nv_bfloat162 -> float2
template<>
struct ggml_cuda_cast_helper<float2, nv_bfloat162, void> {
    static __host__ __device__ inline float2 cast(nv_bfloat162 x) {
#ifdef GGML_USE_HIP
        return make_float2(__bfloat162float(__low2bfloat16(x)), __bfloat162float(__high2bfloat16(x)));
#else
#if __CUDA_ARCH__ >= 800
        return __bfloat1622float2(x);
#else
        return make_float2(__bfloat162float(x.x), __bfloat162float(x.y));
#endif // __CUDA_ARCH__ >= 800
#endif // GGML_USE_HIP
    }
};

// Specialization for float2 -> nv_bfloat162
template<>
struct ggml_cuda_cast_helper<nv_bfloat162, float2, void> {
    static __host__ __device__ inline nv_bfloat162 cast(float2 x) {
#ifdef GGML_USE_HIP
        return __float22bfloat162_rn(x);
#else
        return {x.x, x.y};
#endif // GGML_USE_HIP
    }
};

// Specialization for int32_t destination
template<typename src_t>
struct ggml_cuda_cast_helper<int32_t, src_t, void> {
    static __host__ __device__ inline int32_t cast(src_t x) {
        return int32_t(x);
    }
};

// Main implementation
template<typename dst_t, typename src_t>
__host__ __device__ inline dst_t ggml_cuda_cast_impl(src_t x) {
    return ggml_cuda_cast_helper<dst_t, src_t>::cast(x);
}
