cd /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda

# Fix 1: gated_delta_net.cu - convert if constexpr to tag dispatch
python3 - <<'PY'
p = 'gated_delta_net.cu'
s = open(p).read()

# Fix line 84: if constexpr (!KDA) -> if (!KDA)
s = s.replace(
    '        if constexpr (!KDA) {',
    '        if (!KDA) {'
)

# Fix line 145: if constexpr (keep_rs_t) -> if (keep_rs_t)
s = s.replace(
    '        if constexpr (keep_rs_t) {',
    '        if (keep_rs_t) {'
)

# Fix line 160: if constexpr (!keep_rs_t) -> if (!keep_rs_t)
s = s.replace(
    '    if constexpr (!keep_rs_t) {',
    '    if (!keep_rs_t) {'
)

open(p, 'w').write(s)
print("Fixed gated_delta_net.cu if constexpr")
PY

# Fix 2: mmq.cuh - remove duplicate template declaration
python3 - <<'PY'
p = 'mmq.cuh'
s = open(p).read()

# Remove the duplicate "template <int mmq_x, int mmq_y, bool need_check>" line
old = '''};
template <int mmq_x, int mmq_y, bool need_check>

template <int mmq_x, int mmq_y, bool need_check>
struct mmq_type_traits<mmq_x, mmq_y, need_check, GGML_TYPE_Q4_0> {'''

new = '''};
template <int mmq_x, int mmq_y, bool need_check>
struct mmq_type_traits<mmq_x, mmq_y, need_check, GGML_TYPE_Q4_0> {'''

if old in s:
    s = s.replace(old, new)
    open(p, 'w').write(s)
    print("Fixed mmq.cuh duplicate template")
else:
    print("Pattern not found in mmq.cuh")
PY

# Fix 3: ggml-cuda.cu - fix graph_optimize function pointer type
python3 - <<'PY'
p = 'ggml-cuda.cu'
s = open(p).read()

# Find the graph_optimize line and check the function signature
import re
# The issue is likely that ggml_backend_cuda_graph_optimize has wrong signature
# Let's check what the expected type is
print("Searching for graph_optimize function...")
for m in re.finditer(r'ggml_backend_cuda_graph_optimize', s):
    start = max(0, m.start() - 200)
    end = min(len(s), m.end() + 200)
    print(f"Found at {m.start()}: ...{s[start:end]}...")
    print("---")
PY