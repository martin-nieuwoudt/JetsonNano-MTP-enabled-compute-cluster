# Python Garbage Collection Prevention for Worker Nodes
# From: raw refinements.md — Section: Systems Architecture for Batch Processing
#
# The Python memory manager (pymalloc) hoards memory pools from the OS
# and leaves them fragmented. Explicitly disable automatic GC and trigger
# page sweeps manually during execution micro-pauses.

import gc
import ctypes

# Disable automatic random sweeping
gc.disable()

def post_batch_cleanup():
    gc.collect()
    # Force glibc to return unused heap memory areas back to the Linux Kernel
    ctypes.CDLL('libc.so.6').malloc_trim(0)