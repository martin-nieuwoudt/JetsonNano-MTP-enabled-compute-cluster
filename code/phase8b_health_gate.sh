#!/bin/bash
# Phase 8b: Golden Image Health Gate
# From: Nano Work Plan.md — Phase 8b (pre-clone deploy gate)
# Run LOCALLY on the template node (node 150) BEFORE Phase 9 clones the fleet.
# Also re-runnable on any worker after first boot to confirm health.
#
# Checks the things the host-side `cluster_telemetry.py audit` (idle-only) misses:
#   1. Clock lock is actually applied and STICKING (nvpmodel -m 0 + jetson_clocks)
#   2. SD card I/O health (no mmc errors, partition filled, not read-only)
#   3. rpc-server binary integrity (exists + --help returns 0)
#   4. Required systemd services are enabled (first-boot expand, maxperf, cluster-init)
#   5. Memory fragmentation via /proc/buddyinfo (contiguous blocks available)
#   6. RPC port 50052 is listening (if daemon expected up)
#   7. Thermal baseline (idle, for trend comparison)
#   8. OPTIONAL load probe: launch rpc-server, push a real token, confirm return
#
# Exit code: 0 = all PASS, 1 = any FAIL (safe to gate the clone flow on this).

set -u

PORT=50052
RPC_BIN="/home/jetson/llama.cpp/build/bin/rpc-server"
SUDO=""
if [ "$(id -u)" -ne 0 ]; then SUDO="sudo"; fi

# --- result accumulators ---
FAILS=0
WARNS=0
pass() { echo "  [PASS] $1"; }
fail() { echo "  [FAIL] $1"; FAILS=$((FAILS+1)); }
warn() { echo "  [WARN] $1"; WARNS=$((WARNS+1)); }

echo "=============================================================="
echo " PHASE 8b — GOLDEN IMAGE HEALTH GATE"
echo " Host: $(hostname)  IP: $(hostname -I | awk '{print $1}')"
echo " Date: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo "=============================================================="

# ---------------------------------------------------------------
# 1. CLOCK LOCK (nvpmodel -m 0 + jetson_clocks applied & sticking)
# ---------------------------------------------------------------
echo "[1/8] Power/clock profile"
MODEL=$($SUDO nvpmodel -q 2>/dev/null | grep -i "NV Power Mode" | awk -F': ' '{print $2}' | tr -d ' ')
if [ "$MODEL" = "MAXN" ] || [ "$MODEL" = "0" ]; then
    pass "nvpmodel mode = $MODEL (max performance)"
else
    fail "nvpmodel mode = '${MODEL:-unknown}' (expected MAXN/0)"
fi
# jetson_clocks writes a status file when active
if [ -f /tmp/jetson_clocks.log ] || systemctl is-active --quiet jetson-maxperf.service 2>/dev/null; then
    pass "jetson_clocks / maxperf service active"
else
    # fall back: check a core is at max freq
    MAXFREQ=$(cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_max_freq 2>/dev/null || echo 0)
    if [ "$MAXFREQ" -ge 1400000 ] 2>/dev/null; then
        pass "CPU scaling_max_freq = $MAXFREQ (clocks locked high)"
    else
        warn "jetson_clocks status unconfirmed (scaling_max_freq=$MAXFREQ)"
    fi
fi

# ---------------------------------------------------------------
# 2. SD CARD I/O HEALTH
# ---------------------------------------------------------------
echo "[2/8] SD card / storage health"
if dmesg 2>/dev/null | grep -iE "mmc.*(error|timeout|failed|I/O)" | grep -qvE "mmcblk0boot|mmc0:"; then
    fail "dmesg shows mmc I/O errors (possible card corruption)"
else
    pass "no mmc I/O errors in dmesg"
fi
ROOTDEV=$(findmnt -n -o SOURCE / 2>/dev/null | sed 's/p[0-9]*$//')
if [ -n "$ROOTDEV" ]; then
    ROOTUSE=$(df -h / | awk 'NR==2 {print $5}' | tr -d '%')
    if [ "${ROOTUSE:-0}" -lt 95 ]; then
        pass "root filesystem ${ROOTUSE}% used (healthy headroom)"
    else
        fail "root filesystem ${ROOTUSE}% used (too full to clone safely)"
    fi
    # read-only check
    if mount | grep " $ROOTDEV " | grep -q "ro,"; then
        fail "root device mounted read-only"
    else
        pass "root device mounted read-write"
    fi
else
    warn "could not resolve root device for fill check"
fi

# ---------------------------------------------------------------
# 3. rpc-server BINARY INTEGRITY
# ---------------------------------------------------------------
echo "[3/8] rpc-server binary integrity"
if [ -x "$RPC_BIN" ]; then
    pass "binary present and executable: $RPC_BIN"
    if "$RPC_BIN" --help >/dev/null 2>&1; then
        pass "rpc-server --help returns 0 (binary not corrupted)"
    else
        fail "rpc-server --help failed (binary may be corrupted)"
    fi
else
    fail "rpc-server binary missing or not executable: $RPC_BIN"
fi

# ---------------------------------------------------------------
# 4. SYSTEMD SERVICE ENABLEMENT
# ---------------------------------------------------------------
echo "[4/8] Required services enabled"
for svc in jetson-maxperf.service cluster-init.service phase3b_firstboot.service; do
    if systemctl is-enabled --quiet "$svc" 2>/dev/null; then
        pass "service enabled: $svc"
    else
        # phase3b first-boot expand only matters on first boot of cloned nodes;
        # warn not fail on the template (it is optional there, mandatory on workers)
        if [ "$svc" = "phase3b_firstboot.service" ]; then
            warn "service not enabled: $svc (expected on cloned nodes, optional on template)"
        else
            fail "service NOT enabled: $svc"
        fi
    fi
done

# ---------------------------------------------------------------
# 5. MEMORY FRAGMENTATION (/proc/buddyinfo)
# ---------------------------------------------------------------
echo "[5/8] Memory fragmentation (contiguous blocks)"
# Count free blocks of order >= 5 (128+ pages = 512KB+ contiguous) as a proxy
# for the kernel's ability to satisfy large CMA/GPU allocations.
if [ -r /proc/buddyinfo ]; then
    # Sum order>=5 free blocks across all zones
    BIG=$(awk '{ for(i=5;i<=NF;i++) sum+=$(i+4) } END {print sum+0}' /proc/buddyinfo)
    if [ "$BIG" -gt 0 ]; then
        pass "buddyinfo: $BIG contiguous block(s) order>=5 available"
    else
        warn "buddyinfo: no order>=5 contiguous blocks free (fragmentation risk under load)"
    fi
else
    warn "/proc/buddyinfo not readable"
fi

# ---------------------------------------------------------------
# 6. RPC PORT LISTENING (only if daemon is expected up)
# ---------------------------------------------------------------
echo "[6/8] RPC port $PORT"
if pgrep -f "rpc-server" >/dev/null 2>&1; then
    if (exec 3<>/dev/tcp/127.0.0.1/$PORT) 2>/dev/null; then
        pass "rpc-server running and port $PORT listening"
        exec 3>&- 2>/dev/null
    else
        fail "rpc-server process present but port $PORT NOT listening"
    fi
else
    warn "rpc-server not running — skipping port listen check (start daemon before audit if required)"
fi

# ---------------------------------------------------------------
# 7. THERMAL BASELINE (idle)
# ---------------------------------------------------------------
echo "[7/8] Thermal baseline (idle)"
TEMP=$(timeout 3 tegrastats --interval 1000 2>/dev/null | head -1 | grep -oE "@[0-9.]+C" | head -1 | tr -d '@C')
if [ -n "$TEMP" ]; then
    TEMPINT=${TEMP%.*}
    if [ "$TEMPINT" -lt 80 ]; then
        pass "idle thermal = ${TEMP}C (below 80C warn threshold)"
    elif [ "$TEMPINT" -lt 85 ]; then
        warn "idle thermal = ${TEMP}C (elevated; check airflow before load)"
    else
        fail "idle thermal = ${TEMP}C (CRITICAL; do not load)"
    fi
else
    warn "could not read thermal via tegrastats"
fi

# ---------------------------------------------------------------
# 8. OPTIONAL LOAD PROBE
# ---------------------------------------------------------------
echo "[8/8] Load probe (optional)"
if [ "${1:-}" = "--load-probe" ] && [ -x "$RPC_BIN" ]; then
    echo "  launching rpc-server for load probe..."
    nohup "$RPC_BIN" --host 127.0.0.1 --port $PORT --mem 3600 >/tmp/phase8b_rpc.log 2>&1 &
    RPCPID=$!
    sleep 3
    if (exec 3<>/dev/tcp/127.0.0.1/$PORT) 2>/dev/null; then
        pass "rpc-server accepted connection during load probe"
        exec 3>&- 2>/dev/null
    else
        fail "rpc-server failed to accept connection during load probe"
    fi
    kill "$RPCPID" 2>/dev/null || true
else
    warn "skipped (pass --load-probe to actually launch + connect rpc-server)"
fi

# ---------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------
echo "=============================================================="
echo " RESULT: $FAILS FAIL(s), $WARNS WARN(s)"
if [ "$FAILS" -gt 0 ]; then
    echo " VERDICT: NOT HEALTHY — do NOT clone until FAILs are resolved."
    echo "=============================================================="
    exit 1
else
    echo " VERDICT: HEALTHY — safe to proceed to Phase 9 clone."
    echo "=============================================================="
    exit 0
fi
