## Phase H: Enable SSD Weight Prewarming (parallel track)

**Goal:** Workers read their weight shard from the NFS-mounted SSD instead of receiving it over TCP. Eliminates the ~200-second weight upload penalty for every inference run.

**Current state (2026-07-15):**
- NFS server installed and running on node0 (`/mnt/ssd` exported)
- All 10 workers have NFS mounted at `/mnt/nano-ssd` (11 GGUF files visible)
- **But:** `rpc-server` binary has no code to read weights from a local path — it only accepts `set_tensor` over TCP
- Every inference pushes the full model (25 GB for DeepSeek-R1) over the 1 Gbps switch

**Approach:** Patch `ggml-rpc-server` to accept a `--model` flag. When present, the server loads its weight shard directly from the NFS path instead of waiting for `set_tensor` RPC calls. The PC client still sends `set_tensor` for the initial handshake but the server ignores redundant uploads for shards it already has.

**Alternative (simpler):** Write a prewarm script that runs on each worker before inference — reads the GGUF from NFS, touches every tensor page to force OS page cache population. After prewarm, NFS reads hit RAM (page cache) instead of the SSD. Does NOT require binary changes.

**Estimated time:**
| Approach | Effort |
|----------|--------|
| Prewarm script (OS page cache) | 1 hour |
| `--model` flag on rpc-server | 4-6 hours (C++ patch + rebuild + test) |

**Recommendation:** Implement the prewarm script first (quick win). Add `--model` flag to rpc-server as a Phase H+ enhancement.

### Phase H-A: Prewarm script (quick win)

```bash
#!/bin/bash
# prewarm_nfs.sh — force OS to cache GGUF pages before inference
GGUF="/mnt/nano-ssd/models/DeepSeek-R1-Distill-Qwen-32B-Q6_K_L.gguf"
echo "Prewarming $GGUF ..."
dd if="$GGUF" of=/dev/null bs=4M status=progress 2>/dev/null
echo "Prewarm complete — pages in RAM cache"
```

Deploy to all 10 workers via SSH. Run before each inference batch. Zero code changes needed.