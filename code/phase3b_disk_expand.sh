#!/bin/bash
# Phase 3b: Expand Root Partition to Fill the SD Card (ALL Nodes)
# From: Nano Work Plan.md — Phase 3b: Disk Expansion (every node)
# Run on EVERY node (template Nano Zero AND each worker) via SSH, once per boot/flash.
#
# PRINCIPLE: whatever the SD card size is, use all of it.
# The flashed JetPack/Qengineering image carves a fixed ~31.3 GB root partition
# regardless of card capacity, leaving the remainder unallocated. This step grows
# the partition and online-resizes the ext4 filesystem to reclaim 100% of the card.
#
# SAFE & IDEMPOTENT:
#   - growpart is a no-op if the partition already spans the disk.
#   - resize2fs is safe to re-run on an already-resized filesystem.
#   - No files are deleted; the build and all data are preserved.
#   - On a 32 GB worker card this reclaims only the small slack (~0.7 GB);
#     on a 64 GB Nano Zero card it reclaims ~31 GB. Either way it is correct.
#   - When launched by code/phase3b_firstboot.service, it runs on EVERY boot.
#     The service no longer uses ConditionFirstBoot= (that condition is never
#     met on cloned images because systemd regenerates /etc/machine-id before
#     the unit is evaluated); idempotency is the guarantee instead.

set -e

# Use sudo only when not already root (SSH run as 'jetson' needs it;
# the first-boot systemd service runs as root and must NOT call sudo).
SUDO=""
if [ "$(id -u)" -ne 0 ]; then SUDO="sudo"; fi

echo "[PHASE 3b] Expanding root partition to fill the SD card..."

# --- Resolve the mounted root partition and its parent disk ---------------
ROOT_PART="$($SUDO findmnt -n -o SOURCE /)"
echo "[PHASE 3b] Root partition: $ROOT_PART"

# Derive parent disk and partition number.
# /dev/mmcblk0p1 -> disk=/dev/mmcblk0, part=1
# /dev/sda1      -> disk=/dev/sda,     part=1
if [[ "$ROOT_PART" =~ ^(/dev/mmcblk[0-9]+)p([0-9]+)$ ]]; then
    DISK="${BASH_REMATCH[1]}"
    PART_NUM="${BASH_REMATCH[2]}"
elif [[ "$ROOT_PART" =~ ^(/dev/[a-z]+)([0-9]+)$ ]]; then
    DISK="${BASH_REMATCH[1]}"
    PART_NUM="${BASH_REMATCH[2]}"
else
    echo "[PHASE 3b] ERROR: cannot parse root partition '$ROOT_PART' — aborting." >&2
    exit 1
fi
echo "[PHASE 3b] Parent disk: $DISK  partition #: $PART_NUM"

# --- Before state ---------------------------------------------------------
echo "[PHASE 3b] BEFORE: $($SUDO df -h / | tail -1)"

# --- Ensure growpart is available ----------------------------------------
if ! command -v growpart >/dev/null 2>&1; then
    echo "[PHASE 3b] Installing cloud-guest-utils (provides growpart)..."
    $SUDO apt-get update
    $SUDO apt-get install -y cloud-guest-utils
fi

# --- Grow the partition to the end of the disk ---------------------------
echo "[PHASE 3b] Growing partition $PART_NUM on $DISK ..."
if $SUDO growpart "$DISK" "$PART_NUM" 2>&1; then
    echo "[PHASE 3b] Partition grown (or already maximal)."
else
    echo "[PHASE 3b] growpart reported no change — partition already fills the disk."
fi

# --- Online-resize the ext4 filesystem ------------------------------------
echo "[PHASE 3b] Resizing ext4 filesystem online..."
$SUDO resize2fs "$ROOT_PART"

# --- After state ----------------------------------------------------------
echo "[PHASE 3b] AFTER:  $(df -h / | tail -1)"
echo "[PHASE 3b] Disk expansion complete. No files were deleted."
