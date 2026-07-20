#!/bin/bash
set -e
cd /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda

echo "=== Check buffer interface vtable ==="
python3 -c "
p = 'ggml-cuda.cu'
s = open(p).read()
import re
# Find buffer interface vtable
vtables = list(re.finditer(r'static const ggml_backend_buffer_i ggml_backend_cuda_buffer_interface', s))
print(f'Found {len(vtables)} buffer interfaces')
for i, m in enumerate(vtables):
    start = m.start()
    end = s.find('};', start) + 2
    print(f'Buffer vtable {i+1} at {start}:')
    print(s[start:end])
    print('---')
"

echo "=== Check all vtables ==="
python3 -c "
p = 'ggml-cuda.cu'
s = open(p).read()
import re
# Find all vtables
vtables = list(re.finditer(r'static const (ggml_backend_i|ggml_backend_buffer_i) (ggml_backend_cuda_interface|ggml_backend_cuda_buffer_interface)', s))
print(f'Found {len(vtables)} vtables')
for i, m in enumerate(vtables):
    start = m.start()
    end = s.find('};', start) + 2
    print(f'Vtable {i+1} at {start}: {m.group(2)}')
    print(s[start:end])
    print('---')
"