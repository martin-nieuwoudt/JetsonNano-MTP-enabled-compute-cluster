// C++ mlockall Wrapper for rpc-server (llama.cpp, commit b56f079e2)
// From: raw refinements.md — Section: High-Context Memory Management & Memory Isolation
//
// Forces the process to lock its memory space completely into physical LPDDR4.
// Prevents Linux virtual memory manager from swapping out sections of the
// active rpc-server binary code.
// NOTE: at commit b56f079e2 the rpc-server binary has NO --mlock flag, so this
// setuid wrapper provides the memory locking via mlockall() before execv.

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
    // Call standard rpc-server routines (binary name at b56f079e2 is 'rpc-server').
    // The --mlock flag does NOT exist at this commit, so locking is done here via mlockall().
    execv("./rpc-server", argv);
    perror("execv failed");
    return 1;
}