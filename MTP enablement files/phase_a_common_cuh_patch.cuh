// ============================================================
// Phase A patch — ggml/src/ggml-cuda/common.cuh
// Target: NVCC 10.2 / C++14 (no `if constexpr`, no `std::is_same_v`)
// ============================================================

#include <type_traits>

// ------------------------------------------------------------
// 1) Replacement for line 571: C++17 fold-expression is_any<>
// ------------------------------------------------------------
template<typename T, typename... Ts>
struct is_any;

template<typename T, typename U, typename... Ts>
struct is_any<T, U, Ts...>
    : std::integral_constant<bool, std::is_same<T, U>::value || is_any<T, Ts...>::value> {};

template<typename T>
struct is_any<T> : std::false_type {};


// ------------------------------------------------------------
// 2) Lines 578–612: if constexpr chains inside block_reduce_policy
//
// CORRECTION (2026-07-15): The earlier placeholder assumed a generic
// `ggml_cuda_type_ops<T>::op(dst,src,idx)` copy op. That function does
// NOT exist in common.cuh. The real `if constexpr` chains live inside
// `block_reduce_policy<method, T>` (reduce/sentinel for SUM and MAX).
// The correct C++14 conversion is NOT tag dispatch — it is the minimal
// `if constexpr(C) -> if (C)` rewrite, because every discarded branch
// contains only a `static_assert(ggml_cuda_dependent_false_v<T>, ...)`
// (dependent → not instantiated for supported types) or a type-T return
// (consistent return type). This is exactly the pattern llamita.cpp uses.
// A plain `if` on a compile-time bool is optimized away by NVCC 10.2.
// ------------------------------------------------------------

// --- block_reduce_policy<SUM, T>::reduce()  (was line 578) ---
//   if constexpr(is_any<T, float, float2, half2, int>) {
//       return warp_reduce_sum(val);
//   } else {
//       static_assert(ggml_cuda_dependent_false_v<T>, "Unsupported type for block reduce sum");
//   }
// C++14:
    if (is_any<T, float, float2, half2, int>::value) {
        return warp_reduce_sum(val);
    } else {
        static_assert(ggml_cuda_dependent_false_v<T>, "Unsupported type for block reduce sum");
    }

// --- block_reduce_policy<SUM, T>::sentinel()  (was lines 586–592) ---
//   if constexpr (std::is_same_v<T, float>)       { return 0.0f; }
//   else if constexpr (std::is_same_v<T, float2>) { return make_float2(0.0f, 0.0f); }
//   else if constexpr (std::is_same_v<T, half2>)  { return make_half2(0.0f, 0.0f); }
//   else if constexpr (std::is_same_v<T, int>)    { return 0; }
//   else { static_assert(ggml_cuda_dependent_false_v<T>, "..."); }
// C++14:
    if (std::is_same<T, float>::value) {
        return 0.0f;
    } else if (std::is_same<T, float2>::value) {
        return make_float2(0.0f, 0.0f);
    } else if (std::is_same<T, half2>::value) {
        return make_half2(0.0f, 0.0f);
    } else if (std::is_same<T, int>::value) {
        return 0;
    } else {
        static_assert(ggml_cuda_dependent_false_v<T>, "Unsupported type for block reduce sum");
    }

// --- block_reduce_policy<MAX, T>::reduce()  (was line 602) ---
    if (is_any<T, float, half2>::value) {
        return warp_reduce_max(val);
    } else {
        static_assert(ggml_cuda_dependent_false_v<T>, "Unsupported type for block reduce max");
    }

// --- block_reduce_policy<MAX, T>::sentinel()  (was lines 610–612) ---
    if (std::is_same<T, float>::value) {
        return -INFINITY;
    } else if (std::is_same<T, half2>::value) {
        return make_half2(-INFINITY, -INFINITY);
    } else {
        static_assert(ggml_cuda_dependent_false_v<T>, "Unsupported type for block reduce max");
    }

// ------------------------------------------------------------
// 3) Lines 789, 796–804: ggml_cuda_memcpy_1 (value-based branches)
//
// These are value-based (not type-based), so `if constexpr` -> `if` is
// the correct C++14 fix (no tag dispatch needed). The discarded `else`
// holds `static_assert(nbytes == 0 && nbytes == -1, "bad nbytes")`
// which is a compile-time contradiction → fires only for unsupported
// nb_per_cpy, exactly like the original if constexpr.
// ------------------------------------------------------------

//   if constexpr (alignment != 0) {                       // line 789
//       static_assert(nbytes % alignment == 0, "bad alignment");
//   }
// C++14:
    if (alignment != 0) {
        static_assert(nbytes % alignment == 0, "bad alignment");
    }

//   constexpr int nb_per_cpy = alignment == 0 ? nbytes : alignment;
//   ... #pragma unroll loop over nbytes/nb_per_cpy ...
//   if constexpr (nb_per_cpy == 1)  { ((char *) dst)[i] = ((const char *) src)[i]; }
//   else if constexpr (nb_per_cpy == 2)  { ((short *) dst)[i] = ((const short *) src)[i]; }
//   else if constexpr (nb_per_cpy == 4)  { ((int *) dst)[i] = ((const int *) src)[i]; }
//   else if constexpr (nb_per_cpy == 8)  { ((int2 *) dst)[i] = ((const int2 *) src)[i]; }
//   else if constexpr (nb_per_cpy == 16) { ((int4 *) dst)[i] = ((const int4 *) src)[i]; }
//   else { static_assert(nbytes == 0 && nbytes == -1, "bad nbytes"); }
// C++14:
    if (nb_per_cpy == 1) {
        ((char *) dst)[i] = ((const char *) src)[i];
    } else if (nb_per_cpy == 2) {
        ((short *) dst)[i] = ((const short *) src)[i];
    } else if (nb_per_cpy == 4) {
        ((int *) dst)[i] = ((const int *) src)[i];
    } else if (nb_per_cpy == 8) {
        ((int2 *) dst)[i] = ((const int2 *) src)[i];
    } else if (nb_per_cpy == 16) {
        ((int4 *) dst)[i] = ((const int4 *) src)[i];
    } else {
        static_assert(nbytes == 0 && nbytes == -1, "bad nbytes");
    }
