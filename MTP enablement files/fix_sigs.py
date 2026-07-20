p = 'ggml-cuda.cu'
s = open(p).read()

# Fix graph_optimize signature
old = 'static void ggml_backend_cuda_graph_optimize(ggml_backend_t backend, ggml_cgraph * cgraph) {'
new = 'static void ggml_backend_cuda_graph_optimize(ggml_backend_t backend, ggml_backend_graph_plan_t graph_plan) {'
if old in s:
    s = s.replace(old, new)
    print('Fixed graph_optimize signature')
else:
    print('graph_optimize signature not found')

# Fix buffer init_tensor signature
old2 = 'static enum ggml_status ggml_backend_cuda_buffer_init_tensor(ggml_backend_buffer_t buffer, ggml_tensor * tensor) {'
new2 = 'static void ggml_backend_cuda_buffer_init_tensor(ggml_backend_buffer_t buffer, ggml_tensor * tensor) {'
if old2 in s:
    s = s.replace(old2, new2)
    print('Fixed buffer init_tensor signature')
else:
    print('buffer init_tensor signature not found')

# Fix buffer cpy_tensor signature
old6 = 'static bool ggml_backend_cuda_buffer_cpy_tensor(ggml_backend_buffer_t buffer, const ggml_tensor * src, ggml_tensor * dst) {'
new6 = 'static void ggml_backend_cuda_buffer_cpy_tensor(ggml_backend_buffer_t buffer, const ggml_tensor * src, ggml_tensor * dst) {'
if old6 in s:
    s = s.replace(old6, new6)
    print('Fixed buffer cpy_tensor signature')
else:
    print('buffer cpy_tensor signature not found or already correct')

open(p, 'w').write(s)
print('Done fixing signatures')