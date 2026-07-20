# Zero-Copy CUDA Allocation for Jetson Nano (Maxwell SM 5.3)
# From: raw refinements.md — Section 2: Shared Memory Star Topology Architecture
#
# The Jetson Nano's Maxwell GPU can access CPU memory arrays directly without
# standard cudaMemcpy operations. Use Pinned Host Memory (Mapped Memory) to
# bypass memory duplication, freeing up to 1.5GB of RAM.

# Instead of standard allocation, use page-pinned zero-copy memory
cudaHostAlloc((void**)&host_ptr, size, cudaHostAllocMapped);
cudaHostGetDevicePointer((void**)&dev_ptr, (void*)host_ptr, 0);

# Why this matters: The GPU threads will stream data directly over the shared
# physical LPDDR4 bus. This completely bypasses memory duplication.