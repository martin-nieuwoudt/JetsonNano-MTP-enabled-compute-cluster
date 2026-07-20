#!/bin/bash
# MTP CUDA 10.2 — Phase C & D batch migration script
# Run from: /home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/
set -euo pipefail

echo "== Phase D: std::is_same_v<T, U> -> std::is_same<T, U>::value =="

# Two-arg form: std::is_same_v<T, U>
find . -type f \( -name "*.cu" -o -name "*.cuh" \) -exec sed -i \
  's/std::is_same_v<\([^,]*\),\([^>]*\)>/std::is_same<\1, \2>::value/g' {} +

# Fallback / edge cases: any remaining single-token form
find . -type f \( -name "*.cu" -o -name "*.cuh" \) -exec sed -i \
  's/std::is_same_v<\([^>]*\)>/std::is_same<\1>::value/g' {} +

echo "== Phase D complete. Remaining is_same_v occurrences (should be 0): =="
grep -rn "is_same_v" . || echo "  none found"

echo ""
echo "== Phase C diagnostic: remaining 'if constexpr' requiring manual tag-dispatch =="
grep -rn "if constexpr" . || echo "  none found"

echo ""
echo "Done. Review the 'if constexpr' list above — each occurrence needs the"
echo "tag-dispatch pattern from phase_a_common_cuh_patch.cuh applied by hand;"
echo "this script does not attempt to auto-rewrite those (too structurally"
echo "varied to do safely with sed)."
