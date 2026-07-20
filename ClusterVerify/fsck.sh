#!/bin/bash
for i in $(seq 1 15); do [ -b /dev/sde1 ] && break; sleep 1; done
echo "=== fsck -n (read-only) on /dev/sde1 ==="
fsck -n /dev/sde1 2>&1 | tail -40
echo "=== dmesg tail (I/O errors?) ==="
dmesg | tail -20
