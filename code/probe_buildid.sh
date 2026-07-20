#!/usr/bin/env bash
# Compare the actual ELF build-id of each node's worker vs .150 (the proven one)
ref=$(ssh -o BatchMode=yes jetson@192.168.50.150 'readelf -n /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server 2>/dev/null | grep "Build ID" | awk "{print \$3}"')
echo "REF .150 build-id = $ref"
for n in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$n"
  bid=$(timeout 8 ssh -o BatchMode=yes jetson@$ip 'readelf -n /home/jetson/llama.cpp-mtp/build/bin/ggml-rpc-server 2>/dev/null | grep "Build ID" | awk "{print \$3}"' 2>/dev/null)
  if [ "$bid" = "$ref" ]; then st="MATCH"; else st="DIFFER"; fi
  echo "$ip -> ${bid:-UNREACH} [$st]"
done
