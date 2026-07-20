#!/bin/bash
set -e
IMG_GZ="/mnt/c/Users/marti/Desktop/Cluster/Jetson_NanoZero_Baseline.img.gz"
IMG_RAW="/mnt/c/ClusterVerify/Jetson_NanoZero_Baseline.img"

echo "=== gzip integrity test ==="
gzip -t "$IMG_GZ" && echo "GZIP_OK" || echo "GZIP_BAD"

echo "=== decompress to sparse raw (no full disk use) ==="
# sparse: skip writing zeros, saves space
zcat "$IMG_GZ" | cp --sparse=always /dev/stdin "$IMG_RAW" 2>/dev/null || \
  (echo "cp sparse failed, trying dd"; rm -f "$IMG_RAW"; zcat "$IMG_GZ" > "$IMG_RAW")
echo "raw size: $(du -h --apparent-size "$IMG_RAW" 2>/dev/null | cut -f1)"

echo "=== find rootfs partition (ext4) ==="
# show partition table
fdisk -l "$IMG_RAW" 2>/dev/null | head -30 || parted -s "$IMG_RAW" unit s print 2>/dev/null | head -30
