#!/bin/bash
IMG=/mnt/c/ClusterVerify/Jetson_NanoZero_Baseline.img
echo "=== gdisk -l ==="
gdisk -l "$IMG" 2>&1 || true
echo "=== sgdisk -p ==="
sgdisk -p "$IMG" 2>&1 || true
echo "=== last 34 sectors (GPT backup) present? ==="
SZ=$(stat -c %s "$IMG")
echo "img size bytes=$SZ"
echo "=== try kpartx ==="
kpartx -av "$IMG" 2>&1 || true
ls -l /dev/mapper/ 2>&1 | head
kpartx -dv "$IMG" 2>/dev/null || true
echo DONE
