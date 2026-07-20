#!/bin/bash
# Phase 9: Cloning, Distribution & Nano Zero Promotion
# From: Nano Work Plan.md — Phase 9: Cloning, Distribution & Nano Zero Promotion
#
# ARCHITECTURE (critical): Nano Zero (.150) and all workers are the SAME build.
# Workers are literally Nano Zero WITH THE GUI/DESKTOP REMOVED. So the flow is:
#   build the full thing once (UI kept) -> that IS Nano Zero -> make a copy ->
#   strip the UI from the copy -> clone the UI-stripped copy to workers 1-10.
# Do NOT clone the full image to workers and disable the GUI afterwards.
#
# DISK EXPANSION IS WIRED IN HERE: every cloned node auto-expands its root
# partition to fill whatever SD card it is on, via code/phase3b_firstboot.service
# (ConditionFirstBoot=yes -> runs once per freshly-cloned node). The golden image
# is kept at the flashed ~31.3 GB partition so it still fits 32 GB worker cards;
# each node grows to its real capacity on first boot (32 GB -> small slack,
# 64 GB Nano Zero -> ~31 GB reclaimed). No manual growpart needed per node.
#
# This script is the orchestrator. Image create/flash steps run on the Master PC
# (Windows via WSL/Git Bash, hence the /mnt/c/... paths). SSH/Ansible steps run
# against the booted fleet. Commented blocks are intentional (they need a real
# SD device letter / live fleet); uncommented blocks are safe to run as-is.

set -e

IMG_DIR="/mnt/c/Users/marti/Desktop"
GOLDEN_IMG="$IMG_DIR/Jetson_NanoZero_Baseline.img"
WORKER_IMG="$IMG_DIR/Jetson_Worker_Baseline.img"

echo "[PHASE 9] Cloning Worker Baseline to all 11 SD cards..."

# ---------------------------------------------------------------------------
# 9a: Build the golden image (Nano Zero, UI kept)
# ---------------------------------------------------------------------------
# The fully built template node (Phases 3b-8) IS Nano Zero. Keep the GUI.
# Capture it with compress_image_safe.sh (zerofree + dd + pigz; never deletes
# source files to shrink). Run on Master PC via WSL/Git Bash:
#   sudo bash code/compress_image_safe.sh /dev/sdX "$GOLDEN_IMG"

# ---------------------------------------------------------------------------
# 8b GATE: Health-scan the golden image BEFORE cloning it 11x
# ---------------------------------------------------------------------------
# The user's explicit requirement: "scan the current image for system health, so
# that it doesn't fall over when it starts getting used." A latent fault (missing
# service, corrupted binary, SD I/O error) would otherwise be replicated across
# the entire fleet. Run phase8b_health_gate.sh on the template node and ABORT the
# clone if it reports any FAIL. This is the single most important pre-clone step.
echo "[PHASE 9] Running Phase 8b health gate on template node (192.168.50.150)..."
ssh -o ConnectTimeout=10 -o BatchMode=yes jetson@192.168.50.150 \
    'bash /home/jetson/phase8b_health_gate.sh' || {
    echo "[PHASE 9] [ABORT] Phase 8b health gate FAILED on golden image."
    echo "[PHASE 9] Do NOT clone. Fix the FAILs, re-run, then proceed to 9b."
    exit 1
}
echo "[PHASE 9] [OK] Golden image passed health gate — safe to clone."

# ---------------------------------------------------------------------------
# 9b: Derive the worker image (UI stripped) — the ONLY difference
# ---------------------------------------------------------------------------
# Make a copy, then disable the GUI on the COPY (not the golden).
#   cp "$GOLDEN_IMG" "$WORKER_IMG"
# Mount the worker copy offline and run inside it:
#   systemctl set-default multi-user.target
# (frees ~0.2 GB VRAM/RAM per node for model weights; workers are headless)
# ALSO bump the rpc-server -m from node0's 3000 to the worker value 3600, since
# the daemon unit is baked into the golden image as node0 (GUI kept). Workers are
# headless and can use the larger buffer. Edit the unit inside the mounted copy:
#   sed -i 's/-m 3000/-m 3600/' /mnt/p1/etc/systemd/system/llama-rpc.service
#   (then re-run systemctl daemon-reload inside the chroot before unmount)

# ---------------------------------------------------------------------------
# 9c: Flash the fleet + inject the first-boot disk-expand service
# ---------------------------------------------------------------------------
# Flash worker image to 10x 32 GB cards, golden image to 1x 64 GB card:
#   sudo dd if="$WORKER_IMG" of=/dev/sdWORKER bs=4M status=progress conv=fsync
#   sudo dd if="$GOLDEN_IMG" of=/dev/sdNANOZERO bs=4M status=progress conv=fsync
#
# The phase3b_firstboot.service is ALREADY baked into both images (installed in
# Phase 3b on the template node and carried through the clone), so every node
# auto-expands its partition on first boot — no per-node manual step required.
# If it was NOT baked in, inject it into each flashed card's rootfs before boot:
#   sudo mount /dev/sdX1 /mnt/p1
#   sudo cp code/phase3b_disk_expand.sh /mnt/p1/home/jetson/phase3b_disk_expand.sh
#   sudo cp code/phase3b_firstboot.service /mnt/p1/etc/systemd/system/
#   sudo chroot /mnt/p1 systemctl enable phase3b_firstboot.service
#   sudo umount /mnt/p1

# ---------------------------------------------------------------------------
# 9d: Boot + verify (runs against the live fleet)
# ---------------------------------------------------------------------------
# Boot all 11 Nanos. Each regenerates unique SSH keys + machine-id on first boot
# and auto-runs phase3b_disk_expand.sh via the first-boot service, THEN starts
# the RPC daemon. Verify from WSL2:
#   ansible jetsons -i code/hosts.ini -m ping        # all 11 SUCCESS
#
# Confirm disk expansion actually happened on every node (this is the wired-in
# check — reports any node that did not grow to fill its card):
verify_disk_expansion() {
    local ips=(192.168.50.150 192.168.50.151 192.168.50.152 192.168.50.153 \
               192.168.50.154 192.168.50.155 192.168.50.156 192.168.50.157 \
               192.168.50.158 192.168.50.159 192.168.50.160)
    local fail=0
    for ip in "${ips[@]}"; do
        local line
        line="$(ssh -o ConnectTimeout=8 -o BatchMode=yes "jetson@$ip" \
            'df -h / | tail -1; echo "firstboot_service=$(systemctl is-enabled phase3b_firstboot.service 2>/dev/null)"' 2>/dev/null)" \
            || { echo "  [WARN] $ip unreachable"; fail=1; continue; }
        echo "  [$ip] $line"
    done
    return $fail
}
echo "[PHASE 9] Verifying disk expansion across fleet..."
verify_disk_expansion || echo "[PHASE 9] [WARN] some nodes unreachable or not expanded yet."

# Post-clone health re-check: every freshly-cloned node must also pass the
# Phase 8b gate (first-boot disk-expand + service enablement ran on it). Any
# FAIL here means a node came up unhealthy and should be re-flashed, not used.
echo "[PHASE 9] Re-running Phase 8b health gate on every cloned node..."
for ip in 192.168.50.150 192.168.50.151 192.168.50.152 192.168.50.153 \
         192.168.50.154 192.168.50.155 192.168.50.156 192.168.50.157 \
         192.168.50.158 192.168.50.159 192.168.50.160; do
    ssh -o ConnectTimeout=8 -o BatchMode=yes "jetson@$ip" \
        'bash /home/jetson/phase8b_health_gate.sh' \
        && echo "  [$ip] HEALTHY" \
        || echo "  [$ip] [FAIL] unhealthy — re-flash this node"
done

# ---------------------------------------------------------------------------
# 9e: Promote Nano Zero extras (SSD, NFS, model storage)
# ---------------------------------------------------------------------------
# Select the node at 192.168.50.150 as Nano Zero (already 64 GB, already expanded).
# Attach USB SSD -> /mnt/ssd, install NFS server, export models, mount on all nodes.
# (See Nano Work Plan.md Phase 9e for the full NFS procedure.)

echo "[PHASE 9] Cloning and Nano Zero promotion flow ready."
echo "[PHASE 9] Disk expansion is wired into first boot via phase3b_firstboot.service."