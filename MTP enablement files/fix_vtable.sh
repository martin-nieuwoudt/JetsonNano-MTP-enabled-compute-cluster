#!/bin/bash
set -e
cd /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda

echo "=== Fix ggml-cuda.cu vtable to match stable tree ==="
python3 -c "
p = 'ggml-cuda.cu'
s = open(p).read()

# Find the backend vtable (the one at line ~4246)
import re
vtables = list(re.finditer(r'static const ggml_backend_i ggml_backend_cuda_interface', s))
print(f'Found {len(vtables)} backend interfaces')

for i, m in enumerate(vtables):
    start = m.start()
    end = s.find('};', start) + 2
    print(f'Vtable {i+1} at {start}:')
    print(s[start:end])
    print('---')

# The first one (around line 4246) is the problematic one
# We need to replace it with the stable tree's simpler vtable
# Let's find the exact boundaries of the first vtable
first_start = vtables[0].start()
first_end = s.find('};', first_start) + 2

# Stable tree vtable structure (from earlier inspection):
stable_vtable = '''static const ggml_backend_i ggml_backend_cuda_interface = {
    /* .get_name                = */ ggml_backend_cuda_get_name,
    /* .free                    = */ ggml_backend_cuda_free,
    /* .set_tensor_async        = */ ggml_backend_cuda_set_tensor_async,
    /* .get_tensor_async        = */ ggml_backend_cuda_get_tensor_async,
    /* .cpy_tensor_async        = */ ggml_backend_cuda_cpy_tensor_async,
    /* .synchronize             = */ ggml_backend_cuda_synchronize,
    /* .graph_plan_create       = */ NULL,
    /* .graph_plan_free         = */ NULL,
    /* .graph_plan_update       = */ NULL,
    /* .graph_plan_compute      = */ NULL,
    /* .graph_compute           = */ ggml_backend_cuda_graph_compute,
    /* .event_record            = */ ggml_backend_cuda_event_record,
    /* .event_wait              = */ ggml_backend_cuda_event_wait,
};'''

# Replace the first vtable
s = s[:first_start] + stable_vtable + s[first_end:]

open(p, 'w').write(s)
print('Replaced first vtable with stable tree version')
"