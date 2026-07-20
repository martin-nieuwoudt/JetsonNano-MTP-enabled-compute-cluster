// ============================================================
// Phase B patch — ggml/src/ggml-cuda/convert.cuh
// Target: NVCC 10.2 / C++14
// ============================================================

#include <type_traits>

// C++14 SFINAE replacement for ggml_cuda_cast_impl
// (fixes template deduction errors reported against the earlier
// partial C++14 rewrite)

template <typename T, typename U>
__device__ __forceinline__
typename std::enable_if<std::is_same<T, U>::value, T>::type
ggml_cuda_cast_impl(U val) {
    return val;
}

template <typename T, typename U>
__device__ __forceinline__
typename std::enable_if<!std::is_same<T, U>::value, T>::type
ggml_cuda_cast_impl(U val) {
    return static_cast<T>(val);
}
