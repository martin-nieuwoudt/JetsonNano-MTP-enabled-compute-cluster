#!/bin/bash
cd /home/jetson/llama.cpp-mtp
F=ggml/src/ggml-cuda/ggml-cuda.cu
for L in 107 111 410 604 617 901 1385 1790 2293 2298 2305 2310 2318 3981 4027 4034 4322; do
  echo "########## ERROR at $L ##########"
  # print the function signature: nearest preceding line containing 'static' and '(' and ending with '{' or ';'
  awk -v target=$L '
    NR<=target {
      if ($0 ~ /(static|enum ggml_status|void|bool|GGML_UNUSED).*\(.*\)\s*\{?$/) { sig=NR": "$0; depth=0 }
      # also catch multi-line: signature line then {
      if ($0 ~ /^\s*[A-Za-z_].*\(\s*$/) { sig=NR": "$0 }
    }
    END{}
    NR==target { print sig; print target": "$0 }
  ' "$F"
  echo "--- 6 lines before + the line ---"
  sed -n "$((L-6)),${L}p" "$F"
  echo
done
