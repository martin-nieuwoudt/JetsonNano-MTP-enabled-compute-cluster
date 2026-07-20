import re

base = '/home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/'
files = ['common.cuh','dequantize.cuh','vecdotq.cuh','mmq.cuh','mmq.cu','convert.cu','mmvq.cu','ggml-cuda.cu']

def brace_end(lines, start):
    depth = 0; started = False
    for i in range(start, len(lines)):
        for ch in lines[i]:
            if ch == '{': depth += 1; started = True
            elif ch == '}': depth -= 1
        if started and depth <= 0:
            return i
    return len(lines)-1

for fn in files:
    path = base + fn
    with open(path) as f:
        lines = f.readlines()
    kill = set()
    i = 0
    while i < len(lines):
        L = lines[i]
        if 'GGML_TYPE_Q1_0_g128' in L or 'g128' in L:
            s = L.strip()
            # function definition (static __device__ ... g128 ( )
            if 'static __device__' in L and 'g128' in L and '(' in L:
                end = brace_end(lines, i)
                for j in range(i, end+1): kill.add(j)
                i = end+1; continue
            # ggml_cuda_type_traits<GGML_TYPE_Q1_0_g128> { ... };
            if 'ggml_cuda_type_traits' in L and 'GGML_TYPE_Q1_0_g128' in L:
                end = brace_end(lines, i)
                if i-1 >= 0 and lines[i-1].strip() == 'template<>':
                    kill.add(i-1)
                for j in range(i, end+1): kill.add(j)
                i = end+1; continue
            # struct mmq_type_traits<...GGML_TYPE_Q1_0_g128> { ... };
            if 'struct mmq_type_traits' in L and 'GGML_TYPE_Q1_0_g128' in L:
                end = brace_end(lines, i)
                for j in range(i, end+1): kill.add(j)
                i = end+1; continue
            # case statement
            if s.startswith('case GGML_TYPE_Q1_0_g128:'):
                if 'return' in L:
                    kill.add(i); i += 1; continue
                j = i+1
                while j < len(lines) and lines[j].strip() == '': j += 1
                nxt = lines[j].strip() if j < len(lines) else ''
                if nxt.startswith('return'):
                    kill.add(i); kill.add(j); i = j+1; continue
                if nxt.startswith('mul_mat_q_case') or nxt.startswith('mul_mat_vec_q_switch_ncols_dst'):
                    k = j
                    while k < len(lines) and 'break;' not in lines[k]:
                        k += 1
                    if k < len(lines): k += 1
                    for x in range(i, k): kill.add(x)
                    i = k; continue
                kill.add(i); i += 1; continue
            # single line: define / static_assert / extern DECL / etc.
            kill.add(i); i += 1; continue
        i += 1
    keep = [lines[x] for x in range(len(lines)) if x not in kill]
    with open(path, 'w') as f:
        f.writelines(keep)
    print("%s: deleted %d lines" % (fn, len(kill)))

# final verification
import subprocess
print("=== remaining g128 references (should be 0) ===")
for fn in files:
    with open(base+fn) as f:
        c = sum(1 for l in f if 'g128' in l or 'GGML_TYPE_Q1_0_g128' in l)
    if c: print("%s: %d" % (fn, c))
print("done")
