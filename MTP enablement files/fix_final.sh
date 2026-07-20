#!/bin/bash
set -e
cd /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda

echo "=== Fix buffer cpy_tensor return type ==="
python3 -c "
p = 'ggml-cuda.cu'
s = open(p).read()

# Fix cpy_tensor return type from void to bool
old = '''static void ggml_backend_cuda_buffer_cpy_tensor(ggml_backend_buffer_t buffer, const ggml_tensor * src, ggml_tensor * dst) {'''
new = '''static bool ggml_backend_cuda_buffer_cpy_tensor(ggml_backend_buffer_t buffer, const ggml_tensor * src, ggml_tensor * dst) {'''

if old in s:
    s = s.replace(old, new)
    # Also need to change return statements
    s = s.replace('return;', 'return true;')
    open(p, 'w').write(s)
    print('Fixed cpy_tensor return type')
else:
    print('cpy_tensor pattern not found')
"

echo "=== Remove graph_optimize from vtable (not in stable tree) ==="
python3 -c "
p = 'ggml-cuda.cu'
s = open(p).read()

# The vtable has graph_optimize but stable tree doesn't
# Find the vtable and remove the graph_optimize line
import re
vtables = list(re.finditer(r'static const ggml_backend_i ggml_backend_cuda_interface', s))
for i, m in enumerate(vtables):
    start = m.start()
    end = s.find('};', start) + 2
    print(f'Vtable {i+1} at {start}:')
    print(s[start:end])
    print('---')
"