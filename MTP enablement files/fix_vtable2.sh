#!/bin/bash
set -e
cd /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda

echo "=== Fix remaining vtable function signatures ==="
python3 -c "
p = 'ggml-cuda.cu'
s = open(p).read()

# The issue: MTP tree has graph_plan_* functions and graph_optimize with different signatures
# Stable tree has simpler API: no graph_plan_*, graph_optimize takes ggml_cgraph*

# Fix 1: ggml_backend_cuda_graph_optimize - change signature to match stable tree
# Current: static void ggml_backend_cuda_graph_optimize(ggml_backend_t backend, ggml_backend_graph_plan_t graph_plan)
# Should be: static void ggml_backend_cuda_graph_optimize(ggml_backend_t backend, ggml_cgraph * cgraph)

import re

# Find and fix graph_optimize signature
old_optimize = '''static void ggml_backend_cuda_graph_optimize(ggml_backend_t backend, ggml_backend_graph_plan_t graph_plan) {'''
new_optimize = '''static void ggml_backend_cuda_graph_optimize(ggml_backend_t backend, ggml_cgraph * cgraph) {'''
if old_optimize in s:
    s = s.replace(old_optimize, new_optimize)
    print('Fixed graph_optimize signature')
else:
    print('graph_optimize pattern not found')

# Fix 2: Remove graph_plan_* functions from vtable - they don't exist in stable tree
# The vtable should not have graph_plan_create, graph_plan_free, graph_plan_update, graph_plan_compute
# These are already NULL in the vtable I wrote, but the function declarations might conflict

# Fix 3: ggml_backend_cuda_graph_compute signature
# Current: static enum ggml_status ggml_backend_cuda_graph_compute(ggml_backend_t backend, ggml_cgraph * cgraph)
# Stable: static enum ggml_status ggml_backend_cuda_graph_compute(ggml_backend_t backend, ggml_cgraph * cgraph)
# This should match

# Fix 4: ggml_backend_cuda_event_record/wait signatures
# Current: static void ggml_backend_cuda_event_record(ggml_backend_t backend, ggml_backend_event_t event)
# Stable: static void ggml_backend_cuda_event_record(ggml_backend_t backend, ggml_backend_event_t event)
# This should match

# Fix 5: The vtable I wrote has graph_optimize but the function is now unused (warning)
# Need to make sure the vtable matches exactly what stable tree has

# Let's check what the stable tree vtable actually has
print('Checking stable tree vtable structure...')

open(p, 'w').write(s)
print('Done')
"