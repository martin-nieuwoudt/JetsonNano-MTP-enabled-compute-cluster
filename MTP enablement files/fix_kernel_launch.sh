cd /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda
# Add the missing kernel launch helpers to common.cuh
# Insert before the last closing brace of the file
python3 - <<'PY'
p = 'common.cuh'
s = open(p).read()

# Find the end of the file - look for the last struct/class definition
# We'll insert before the final closing brace of the file
kernel_launch_helpers = '''

// Kernel launch helper (MTP addition for CUDA 10.2 compatibility)
struct ggml_cuda_kernel_launch_params {
    dim3 grid_dims;
    dim3 block_dims;
    size_t shared_mem_bytes;
    cudaStream_t stream;

    __host__ __device__ ggml_cuda_kernel_launch_params() : grid_dims(1,1,1), block_dims(1,1,1), shared_mem_bytes(0), stream(0) {}
    __host__ __device__ ggml_cuda_kernel_launch_params(dim3 grid, dim3 block, size_t shmem, cudaStream_t strm)
        : grid_dims(grid), block_dims(block), shared_mem_bytes(shmem), stream(strm) {}
};

template <typename Kernel, typename... Args>
__host__ inline void ggml_cuda_kernel_launch(Kernel kernel, const ggml_cuda_kernel_launch_params & params, Args... args) {
    kernel<<<params.grid_dims, params.block_dims, params.shared_mem_bytes, params.stream>>>(args...);
}

'''

# Insert before the last few lines (before the final closing brace of the file)
# Find a good spot - after the last struct definition
insert_marker = 'struct ggml_cuda_mm_fusion_args_device {'
idx = s.rfind(insert_marker)
if idx == -1:
    # Fallback: insert near end of file
    idx = s.rfind('};')
    if idx == -1:
        idx = len(s) - 1
else:
    # Find the closing brace of this struct
    idx = s.find('};', idx) + 2

s = s[:idx] + '\n' + kernel_launch_helpers + s[idx:]
open(p, 'w').write(s)
print("Added kernel launch helpers to common.cuh")
PY