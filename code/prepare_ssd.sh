#!/bin/bash
# prepare_ssd.sh — Detect, (optionally) format, and mount the Nano Zero SSD.
# Run via SSH on 192.168.50.150 (the NFS/model-storage node).
#
# SAFETY: This script NEVER formats unless you pass --format AND confirm the
# device on the prompt. Default mode is DETECT-ONLY (read-only).
#
# Usage:
#   bash prepare_ssd.sh            # detect + show what's on the disk (safe)
#   bash prepare_ssd.sh --format   # detect, then format ext4 + mount /mnt/ssd
#
# The work plan (Phase 9c) specifies: ext4, mounted at /mnt/ssd, exported via
# NFS, model symlink at /mnt/ssd/models/current.

set -u
FORMAT=0
[ "${1:-}" = "--format" ] && FORMAT=1

echo "================ DETECT: candidate SSD (non-boot disk) ==============="
# Boot disk is mmcblk0. Any other 'disk' type device is the SSD.
SSD=""
for d in $(lsblk -d -o NAME,TYPE 2>/dev/null | awk '$2=="disk"{print $1}'); do
  [ "$d" = "mmcblk0" ] && continue
  SSD="$d"; break
done
if [ -z "$SSD" ]; then
  echo "  !! No SSD detected (only mmcblk0 / loops / zram present)."
  echo "     Plug the drive in, then re-run."
  exit 1
fi
echo "  Candidate SSD: /dev/$SSD"
lsblk -d -o NAME,SIZE,TYPE,TRAN,ROTA,MODEL "/dev/$SSD" 2>/dev/null
echo
echo "================ CURRENT PARTITION TABLE (read-only) ================"
sudo fdisk -l "/dev/$SSD" 2>/dev/null | sed -n '1,40p'
echo
echo "================ FILESYSTEMS PRESENT ================================"
lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINT "/dev/$SSD"* 2>/dev/null
echo

if [ "$FORMAT" -ne 1 ]; then
  echo "================ MODE: DETECT-ONLY ================================"
  echo "  No changes made. To format as ext4 and mount at /mnt/ssd, re-run:"
  echo "    bash prepare_ssd.sh --format"
  exit 0
fi

# ---- Format path (explicit opt-in only) ----
echo "================ MODE: FORMAT + MOUNT ==============================="
read -r -p "  Type the device to WIPE (e.g. $SSD) to confirm: " CONFIRM
[ "$CONFIRM" = "$SSD" ] || { echo "  Aborted (confirm mismatch)."; exit 1; }

echo "  Unmounting any existing mounts of /dev/$SSD ..."
for m in $(lsblk -n -o MOUNTPOINT "/dev/$SSD"* 2>/dev/null | grep -v '^$'); do
  sudo umount "$m" 2>/dev/null || true
done
echo "  Wiping existing partition table on /dev/$SSD ..."
sudo wipefs -a "/dev/$SSD" >/dev/null 2>&1 || true
echo "  Creating single ext4 partition ..."
echo "  ,,L" | sudo sfdisk "/dev/$SSD" >/dev/null 2>&1
sleep 2
PART="${SSD}p1"; [ "${SSD#mmcblk}" != "$SSD" ] && PART="${SSD}p1" || PART="${SSD}1"
# nvme/sda style -> ${SSD}1 ; mmcblk style -> ${SSD}p1 (handled above)
sudo mkfs.ext4 -F -L nano-ssd "/dev/$PART"
echo "  Mounting at /mnt/ssd ..."
sudo mkdir -p /mnt/ssd
sudo mount "/dev/$PART" /mnt/ssd
sudo chown -R jetson:jetson /mnt/ssd
echo "  /mnt/ssd ready:"
df -h /mnt/ssd
echo
echo "  NOTE: Add to /etc/fstab for persistence (Phase 9c):"
echo "    /dev/$PART  /mnt/ssd  ext4  defaults,noatime  0  2"
