#!/bin/bash
set -e
cd /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda

echo "=== Fix buffer function signatures to match stable tree ==="
python3 - <<'PY'
p = 'ggml-cuda.cu'
s = open(p).read()

# Fix 1: ggml_backend_cuda_buffer_init_tensor - change return type from enum ggml_status to void
old = '''static enum ggml_status ggml_backend_cuda_buffer_init_tensor(ggml_backend_buffer_t buffer, ggml_tensor * tensor) {
    ggml_backend_cuda_buffer_context * ctx = (ggml_backend_cuda_buffer_context *)buffer->context;

    if (tensor->view_src != NULL) {
        assert(tensor->view_src->buffer->buft == buffer->buft);
        return GGML_STATUS_SUCCESS;
    }

    // ... rest of function
    return GGML_STATUS_SUCCESS;
}'''

new = '''static void ggml_backend_cuda_buffer_init_tensor(ggml_backend_buffer_t buffer, ggml_tensor * tensor) {
    ggml_backend_cuda_buffer_context * ctx = (ggml_backend_cuda_buffer_context *)buffer->context;

    if (tensor->view_src != NULL) {
        assert(tensor->view_src->buffer->buft == buffer->buft);
        return;
    }

    // ... rest of function
}'''

# Find the actual function
import re
# Find the init_tensor function
match = re.search(r'static enum ggml_status ggml_backend_cuda_buffer_init_tensor\(.*?\n(?:.*?\n)*?\s*return GGML_STATUS_SUCCESS;\s*\n\}', s, re.DOTALL)
if match:
    func_text = match.group(0)
    # Replace return type
    func_text = func_text.replace('static enum ggml_status ggml_backend_cuda_buffer_init_tensor', 'static void ggml_backend_cuda_buffer_init_tensor')
    # Replace return statements
    func_text = func_text.replace('return GGML_STATUS_SUCCESS;', 'return;')
    s = s[:match.start()] + func_text + s[match.end():]
    print("Fixed init_tensor")
else:
    print("init_tensor pattern not found")

# Fix 2: ggml_backend_cuda_buffer_cpy_tensor - change return type from bool to void
match = re.search(r'static bool ggml_backend_cuda_buffer_cpy_tensor\(.*?\n(?:.*?\n)*?\s*return (true|false);\s*\n\}', s, re.DOTALL)
if match:
    func_text = match.group(0)
    func_text = func_text.replace('static bool ggml_backend_cuda_buffer_cpy_tensor', 'static void ggml_backend_cuda_buffer_cpy_tensor')
    func_text = func_text.replace('return true;', 'return;')
    func_text = func_text.replace('return false;', 'return;')
    s = s[:match.start()] + func_text + s[match.end():]
    print("Fixed cpy_tensor")
else:
    print("cpy_tensor pattern not found")

open(p, 'w').write(s)
print("Done fixing buffer functions")
PY