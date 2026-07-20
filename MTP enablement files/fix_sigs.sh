#!/bin/bash
set -e
cd /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda

echo "=== Fix graph_optimize signature ==="
python3 -c "
p = 'ggml-cuda.cu'
s = open(p).read()

# Fix graph_optimize signature
old = 'static void ggml_backend_cuda_graph_optimize(ggml_backend_t backend, ggml_cgraph * cgraph) {'
new = 'static void ggml_backend_cuda_graph_optimize(ggml_backend_t backend, ggml_backend_graph_plan_t graph_plan) {'

if old in s:
    s = s.replace(old, new)
    open(p, 'w').write(s)
    print('Fixed graph_optimize signature')
else:
    print('graph_optimize signature not found')

# Also check if there are other function signature mismatches
# The vtable expects:
# .set_tensor_async = void (*)(ggml_backend_t, ggml_tensor *, const void *, size_t, size_t, size_t, size_t, size_t)
# .get_tensor_async = void (*)(ggml_backend_t, const ggml_tensor *, void *, size_t, size_t, size_t, size_t, size_t)
# .cpy_tensor_async = void (*)(ggml_backend_t, ggml_backend_t, const ggml_tensor *, ggml_tensor *)

# Let's check the actual function signatures
import re
for func in ['ggml_backend_cuda_set_tensor_async', 'ggml_backend_cuda_get_tensor_async', 'ggml_backend_cuda_cpy_tensor_async']:
    matches = list(re.finditer(r'static.*' + func + r'\([^)]*\)', s))
    for m in matches:
        print(f'{func}: {m.group(0)}')
"

echo "=== Check stable tree function signatures ==="
ssh -o BatchMode=yes -o ConnectTimeout=10 jetson@192.168.50.150 'cd /home/jetson/llama.cpp/ggml/src/ggml-cuda && grep -A3 \"static.*ggml_backend_cuda_set_tensor_async\" ggml-cuda.cu | head -10'
ssh -o BatchMode=yes -o ConnectTimeout=10 jetson@192.168.50.150 'cd /home/jetson/llama.cpp/ggml/src/ggml-cuda && grep -A3 \"static.*ggml_backend_cuda_get_tensor_async\" ggml-cuda.cu | head -10'
ssh -o BatchMode=yes -o ConnectTimeout=10 jetson@192.168.50.150 'cd /home/jetson/llama.cpp/ggml/src/ggml-cuda && grep -A3 \"static.*ggml_backend_cuda_cpy_tensor_async\" ggml-cuda.cu | head -10'