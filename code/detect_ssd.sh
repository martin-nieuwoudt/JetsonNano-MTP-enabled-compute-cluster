#!/bin/bash
# detect_ssd.sh — Characterise any SSD/block device attached to the Jetson Nano.
# Run via SSH. Non-destructive (read-only).
echo "================ BLOCK DEVICES (transport + model) ================"
lsblk -d -o NAME,SIZE,TYPE,TRAN,ROTA,MODEL,SERIAL 2>/dev/null || lsblk -d -o NAME,SIZE,TYPE,ROTA,MODEL 2>/dev/null
echo
echo "================ PCIe NVMe devices (lspci) ========================"
lspci -nn 2>/dev/null | grep -iE 'non-volatile|nvme|sata|ahci|mass storage' || echo "  (no PCIe storage controller listed)"
echo
echo "================ USB storage devices (lsusb) ======================"
lsusb 2>/dev/null | grep -iE 'storage|mass|ssd|sandisk|samsung|wd |seagate|crucial|kingston|nvme' || echo "  (no obvious USB storage in lsusb; full list below)"
lsusb 2>/dev/null
echo
echo "================ NVMe detail (if present) ========================"
for d in /sys/block/nvme*; do
  [ -e "$d" ] || continue
  n=$(basename "$d")
  echo "  $n:"
  echo "    model : $(cat $d/device/model 2>/dev/null)"
  echo "    fw    : $(cat $d/device/firmware_rev 2>/dev/null)"
  echo "    size  : $(( $(cat $d/size 2>/dev/null) * 512 / 1000000000 )) GB ($(cat $d/size 2>/dev/null) sectors)"
  # PCIe link speed/capacity (critical for Jetson Nano Gen2 x1)
  lp="/sys/block/$n/device/../"
  echo "    PCIe  : $(cat $d/device/../link/current_link_speed 2>/dev/null) current / $(cat $d/device/../link/current_link_width 2>/dev/null) lanes"
done
echo
echo "================ SMART health (if smartctl available) ============"
for d in $(lsblk -d -o NAME,TYPE 2>/dev/null | awk '$2=="disk"{print $1}'); do
  if command -v smartctl >/dev/null 2>&1; then
    echo "  /dev/$d:"
    sudo smartctl -i /dev/$d 2>/dev/null | grep -iE 'model|firmware|serial|capacity|health|rotation' || echo "    (smartctl no data)"
  else
    echo "  smartctl not installed (sudo apt install smartmontools for health)"
  fi
done
echo
echo "================ rootfs location ================================"
mount | grep ' / ' | awk '{print $1, $3}'
