// C++ mlockall Wrapper for rpc-server (llama.cpp, commit b56f079e2)
// From: raw refinements.md — Section: High-Context Memory Management & Memory Isolation
// Forces the process to lock its memory space completely into physical LPDDR4.
// Prevents Linux virtual memory manager from swapping out sections of the
// active rpc-server binary code.

#include <sys/mman.h>
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main(int argc, char** argv) {
    // Lock all current and future memory allocations directly into physical RAM
    if (mlockall(MCL_CURRENT | MCL_FUTURE) != 0) {
        perror("mlockall failed - run as sudo");
        return 1;
    }
    // Call standard llama-rpc-server routines via execv (must run from bin dir)
    execv("./rpc-server", argv);
    perror("execv failed");
    return 1;
}
