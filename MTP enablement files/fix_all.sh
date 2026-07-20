#!/bin/bash
set -e
cd /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda

echo "=== Fix 1: gated_delta_net.cu if constexpr ==="
python3 -c "
p = 'gated_delta_net.cu'
s = open(p).read()
s = s.replace('        if constexpr (!KDA) {', '        if (!KDA) {')
s = s.replace('        if constexpr (keep_rs_t) {', '        if (keep_rs_t) {')
s = s.replace('    if constexpr (!keep_rs_t) {', '    if (!keep_rs_t) {')
open(p, 'w').write(s)
print('Fixed gated_delta_net.cu if constexpr')
"

echo "=== Fix 2: mmq.cuh duplicate template ==="
python3 -c "
p = 'mmq.cuh'
s = open(p).read()
import re
# Find double template
for m in re.finditer(r'template <int mmq_x, int mmq_y, bool need_check>\s*\n\s*template <int mmq_x, int mmq_y, bool need_check>', s):
    start = max(0, m.start() - 50)
    end = min(len(s), m.end() + 100)
    print(f'DOUBLE at {m.start()}: ...{s[start:end]}...')
    old = s[m.start():m.end()]
    new = 'template <int mmq_x, int mmq_y, bool need_check>'
    s = s[:m.start()] + new + s[m.end():]
    open(p, 'w').write(s)
    print('Fixed mmq.cuh duplicate template')
    break
else:
    print('No double template found')
"

echo "=== Fix 3: ggml-cuda.cu vtable missing graph_optimize ==="
python3 -c "
p = 'ggml-cuda.cu'
s = open(p).read()
import re
vtables = list(re.finditer(r'static const ggml_backend_i ggml_backend_cuda_interface', s))
print(f'Found {len(vtables)} backend interfaces')
for i, m in enumerate(vtables):
    start = m.start()
    end = s.find('};', start) + 2
    print(f'Vtable {i+1} at {start}:')
    print(s[start:end])
    print('---')
"