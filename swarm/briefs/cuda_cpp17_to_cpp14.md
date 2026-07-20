You are porting CUDA C++ from C++17 to C++14 to compile under NVCC 10.2 on a Jetson Nano (CUDA 10.2, max C++14).
TARGET standard: C++14 (ISO/IEC 14882:2014, N4140). FORBIDDEN in C++14 device code:
 - `if constexpr(...)` at statement scope -> rewrite as plain `if (...)` ONLY when every discarded branch holds only a dependent `static_assert` (then it is semantically identical). Otherwise use tag dispatch / template specialization.
 - `std::is_same_v<T,Ts>` -> `std::is_same<T,Ts>::value`
 - `std::string_view`, `std::filesystem`, `std::optional` (pre-C++17), structured bindings, fold expressions, `std::variant`, `std::any`, `std::byte`, inline variables.
CRITICAL: never replace a real operation body with a stub/(void)0. The known trap is binbcast.cu fold expressions being zeroed -> compiles but produces garbage. Preserve all computation.
Return ONLY the full rewritten file content, no commentary, no markdown fences.
