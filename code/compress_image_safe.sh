#!/bin/bash
# Safe Jetson SD image compression — NEVER deletes a file.
#
# WHY THIS EXISTS:
# A previous "compression" deleted files from the live filesystem to free space.
# That removed system dependencies and the image struggled to boot afterwards.
# This script makes the image SMALL without removing ANYTHING:
#   1. zerofree  -> writes zeros into unused blocks (file contents untouched)
#   2. dd        -> image the card bit-for-bit
#   3. pigz -9   -> compresses the zeros to near-nothing
# Result flashes back IDENTICAL to the original. Boot-safe by construction.
#
# Run on the MASTER PC (Windows via WSL / Git Bash) with the SD card in a USB reader.
# Requires: zerofree, pigz, e2fsprogs (apt install zerofree pigz e2fsprogs).
#
# Usage: sudo ./compress_image_safe.sh <sd-device> <out-image.img>
#   e.g. sudo ./compress_image_safe.sh /dev/sdc Jetson_Worker_Baseline.img

set -euo pipefail

SD_DEV="${1:-}"
OUT_IMG="${2:-}"

if [ -z "$SD_DEV" ] || [ -z "$OUT_IMG" ]; then
  echo "Usage: sudo $0 <sd-device> <out-image.img>" >&2
  exit 1
fi

# --- Safety guards -----------------------------------------------------------
if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: must run as root (sudo)." >&2
  exit 1
fi
if [ ! -b "$SD_DEV" ]; then
  echo "ERROR: $SD_DEV is not a block device." >&2
  exit 1
fi
# Refuse if any partition of the SD is mounted read-write (zerofree needs it off).
if mount | grep -q "${SD_DEV}[0-9].* rw,"; then
  echo "ERROR: a partition on $SD_DEV is mounted read-write. Unmount it first:" >&2
  echo "  umount ${SD_DEV}* " >&2
  exit 1
fi
for tool in zerofree pigz e2fsck dd; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "ERROR: missing required tool: $tool (apt install zerofree pigz e2fsprogs)" >&2
    exit 1
  fi
done

# --- Detect the root partition (the one holding the filesystem) --------------
# Jetson Qengineering image: rootfs is usually partition 1 (mmcblk0p1).
ROOT_PART="${SD_DEV}1"
if [ ! -b "$ROOT_PART" ]; then
  echo "ERROR: expected root partition $ROOT_PART not found." >&2
  exit 1
fi

echo "[SAFE-COMPRESS] Step 1/4: fsck (read-only check) on $ROOT_PART"
e2fsck -fn "$ROOT_PART"

echo "[SAFE-COMPRESS] Step 2/4: zerofree $ROOT_PART (zeros unused blocks, NO file deletion)"
zerofree -v "$ROOT_PART"

echo "[SAFE-COMPRESS] Step 3/4: dd image -> $OUT_IMG"
# Image the whole device (includes partition table + boot sectors).
dd if="$SD_DEV" of="$OUT_IMG" bs=4M status=progress conv=fsync

echo "[SAFE-COMPRESS] Step 4/4: pigz -9 compress -> $OUT_IMG.gz"
pigz -9 -v "$OUT_IMG"

echo "[SAFE-COMPRESS] DONE. Output: $OUT_IMG.gz"
echo "[SAFE-COMPRESS] Flash with:  gunzip -c $OUT_IMG.gz | sudo dd of=$SD_DEV bs=4M status=progress"
echo "[SAFE-COMPRESS] NOTE: image is bit-for-bit identical to source. No files were deleted."
