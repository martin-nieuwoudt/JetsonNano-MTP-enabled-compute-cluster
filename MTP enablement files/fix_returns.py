#!/usr/bin/env python3
# Precise return-type fix for ggml-cuda.cu (MTP CUDA 10.2 port)
# Only touches the 6 void/__global__ functions returning GGML_STATUS_SUCCESS,
# plus adds the missing final return in ggml_cuda_mul_mat_id.
# NO broad sed. Every replacement is an exact, context-anchored string.

import os
base = os.path.expanduser('~/llama.cpp-mtp')
p = 'ggml/src/ggml-cuda/ggml-cuda.cu'
f = os.path.join(base, p)
s = open(f).read()
orig = s
n = 0

def fix(bad, good, label):
    global s, n
    if bad in s:
        s = s.replace(bad, good, 1)
        n += 1
        print('OK   ', label)
    else:
        print('MISS ', label, '-> pattern not found, inspect manually')

# 1) void free(...) override inside ggml_cuda_buffer (line ~410)
fix(
    '                b.ptr = ptr;\n                b.size = size;\n                return GGML_STATUS_SUCCESS;',
    '                b.ptr = ptr;\n                b.size = size;\n                return;',
    'free() override: return;')

# 2) ggml_cuda_set_peer_access (void) line ~1385
fix(
    '    if (peer_access_enabled == enable_peer_access) {\n        return GGML_STATUS_SUCCESS;\n    }',
    '    if (peer_access_enabled == enable_peer_access) {\n        return;\n    }',
    'set_peer_access: return;')

# 3) k_compute_batched_ptrs __global__ void (kernel) line ~1790
fix(
    '    if (i13 >= ne13 || i12 >= ne12) {\n        return GGML_STATUS_SUCCESS;\n    }',
    '    if (i13 >= ne13 || i12 >= ne12) {\n        return;\n    }',
    'k_compute_batched_ptrs: return;')

# 4) ggml_backend_cuda_graph_optimize (void) two early returns 4027 + 4034
fix(
    '    if (!enable_graph_optimization) {\n        return GGML_STATUS_SUCCESS;\n    }',
    '    if (!enable_graph_optimization) {\n        return;\n    }',
    'graph_optimize #1: return;')
fix(
    '    if (!use_cuda_graph || ggml_backend_cuda_get_device_count() != 1) {\n        return GGML_STATUS_SUCCESS;\n    }',
    '    if (!use_cuda_graph || ggml_backend_cuda_get_device_count() != 1) {\n        return;\n    }',
    'graph_optimize #2: return;')

# 5) ggml_backend_cuda_unregister_host_buffer (void) line ~4322
fix(
    '    if (getenv("GGML_CUDA_REGISTER_HOST") == nullptr) {\n        return GGML_STATUS_SUCCESS;\n    }',
    '    if (getenv("GGML_CUDA_REGISTER_HOST") == nullptr) {\n        return;\n    }',
    'unregister_host_buffer: return;')

# 6) ggml_cuda_mul_mat_id (enum ggml_status) missing final return before closing brace
#    The function ends with the get_rows_cuda(...) call then '}'. Add the return.
fix(
    '        nb1, nb2, nb3, stream);\n}',
    '        nb1, nb2, nb3, stream);\n    return GGML_STATUS_SUCCESS;\n}',
    'mul_mat_id: add final return GGML_STATUS_SUCCESS;')

if s != orig:
    open(f, 'w').write(s)
    print('WROTE', n, 'edits to', f)
else:
    print('NO CHANGES MADE')
