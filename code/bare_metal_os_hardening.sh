# Bare-Metal OS Hardening & Memory Extraction for Jetson Nano
# From: raw refinements.md — Section 4
# Drops idle memory usage to ~350-400MB, leaving ~3.6GB free for calculations

# 1. Permanent Headless Transition
sudo systemctl set-default multi-user.target

# 2. Disable the heavy Ubuntu Update Motd and Unattended Upgrades
sudo systemctl disable unattended-upgrades
sudo systemctl stop unattended-upgrades

# 3. Purge standard desktop telemetry and window management bloat
sudo apt-get purge -y lightdm gdm3 ubuntu-desktop x11-common lxde openbox

# 4. Lock the hardware clock to maximum performance profile
sudo nvpmodel -m 0
sudo jetson_clocks

# Note: nvpmodel -m 0 forces the Jetson Nano into its 10W High-Performance Mode,
# unlocking all 4 ARM CPU cores and pinning the GPU clock to its ceiling.
# sudo jetson_clocks locks those clock speeds so the system does not throttle
# down during micro-pauses between orchestration tasks.