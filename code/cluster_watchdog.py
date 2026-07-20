#!/usr/bin/env python3
"""
cluster_watchdog.py — Fault-tolerant RPC orchestration for the 11-node Jetson cluster
=====================================================================================
Purpose: make the Windows-host <-> cluster link SURVIVE the "data barrage".

The llama.cpp RPC protocol is a centralized star: the Windows host holds the model
and ships tensor/activation chunks to every Nano over a single 1GbE uplink. If ONE
node thermal-drops or OOMs mid-generation, llama.cpp RPC aborts the WHOLE generation.
This watchdog closes that gap:

  1. NODE-DROP RE-SLICE: continuously probes RPC port 50052 on every node. When a
     node stops responding, it is removed from the live RPC target set and the
     updated `--rpc` string is printed so the host can re-launch with the surviving
     nodes (e.g. 11 -> 10 -> 9) WITHOUT aborting the session entirely.

  2. THERMAL ACTUATION: reads idle/load thermal via tegrastats. On WARN (>=80C) it
     gracefully drops the hottest node BEFORE it hits the 85C hard-throttle/shutdown
     threshold, preserving the rest of the fleet. On recovery (cooled below 70C) the
     node is re-admitted automatically.

  3. SINGLE SOURCE OF TRUTH: reuses the exact config + collectors from
     cluster_telemetry.py (PORT, JETSON_IPS, THERMAL_* thresholds) so there is never
     a duplicated/divergent definition.

Usage:
  python cluster_watchdog.py                 # run forever, print re-slice events
  python cluster_watchdog.py --once          # single pass, print current live set
  python cluster_watchdog.py --model C:\\Models\\qwen.gguf --prompt "hi"
        # convenience: prints the exact llama-cli.exe invocation for the live set

Requires:  pip install paramiko
"""

import sys
import time
import argparse

# Single source of truth: import authoritative config + collectors from
# mcp/cluster_config.py (the one place node IPs / ports / SSH / thermal live).
# Collectors (check_rpc_port, get_node_ssh) come from cluster_telemetry, which
# itself imports the same config — so there is exactly ONE definition of each.
try:
    from mcp.cluster_config import (
        RPC_PORT as PORT, NODE_IPS as JETSON_IPS,
        THERMAL_WARN_C, THERMAL_FAIL_C, THERMAL_REJOIN_C,
        SSH_USER, SSH_KEY_PATH, PROBE_INTERVAL_SEC,
        RPC_DAEMON_M_NODE0, RPC_DAEMON_M_WORKER,
        get_cluster_mode, CLUSTER_MODE_MAINTENANCE,
    )
    from cluster_telemetry import get_node_ssh, check_rpc_port
    import cluster_qos as qos
except Exception as _imp_err:
    print(f"[WATCHDOG] config/telemetry/qos import failed ({_imp_err}); aborting.",
          file=sys.stderr)
    sys.exit(1)


def rpc_string(active_ips):
    """Build the canonical --rpc target string from the live node set."""
    return ",".join(f"{ip}:{PORT}" for ip in active_ips)


def probe_node(ip):
    """Return (rpc_up:bool, temp_c:float|None) for one node."""
    rpc_up = check_rpc_port(ip)
    _, _, temp_c = get_node_ssh(ip)
    return rpc_up, temp_c


def _handle_thermal(ip, temp_c, active, dropped_thermal, events):
    """Apply thermal actuation rules. Returns True if node is live after thermal check."""
    # Thermal actuation: drop hottest node BEFORE hard throttle/shutdown
    if temp_c is not None and temp_c >= THERMAL_WARN_C:
        if ip in active and ip not in dropped_thermal:
            dropped_thermal.add(ip)
            active.discard(ip)
            events.append(f"[THERMAL] {ip} {temp_c:.1f}C >= {THERMAL_WARN_C:.0f}C WARN -> gracefully DROPPED (preserve fleet)")
        return False

    # Re-admit cooled node
    if temp_c is not None and temp_c < THERMAL_REJOIN_C and ip in dropped_thermal:
        dropped_thermal.discard(ip)
        active.add(ip)
        events.append(f"[COOLED] {ip} {temp_c:.1f}C < {THERMAL_REJOIN_C:.0f}C -> re-admitted")

    return ip in active


def decide_node(ip, rpc_up, temp_c, active, dropped_thermal, dropped_dead, events):
    """Apply fault-tolerance rules for one node; mutate state sets; return True if live.

    Resilience is owned HERE and uses ONE relaunch implementation (qos.relaunch_rpc_daemon)
    — there is no second, divergent relaunch path elsewhere.
    """
    # Dead node (RPC down): attempt ONE relaunch via the shared QoS helper.
    # Only drop from the live set if the relaunch fails (operator must investigate).
    if not rpc_up:
        if ip in active and ip not in dropped_dead:
            m = RPC_DAEMON_M_NODE0 if ip == JETSON_IPS[0] else RPC_DAEMON_M_WORKER
            events.append(f"[DEAD] {ip} RPC port {PORT} closed -> attempting relaunch")
            if qos.relaunch_rpc_daemon(ip, port=PORT, m=m):
                events.append(f"[RELAUNCH] {ip} rpc-server back up -> kept in live set")
                return True
            dropped_dead.add(ip)
            active.discard(ip)
            events.append(f"[DEAD] {ip} relaunch FAILED -> DROPPED from live set")
        return ip in active

    if ip in dropped_dead:  # RPC restored -> re-admit
        dropped_dead.discard(ip)
        events.append(f"[RECOVER] {ip} RPC restored -> re-admitted")
        active.add(ip)

    return _handle_thermal(ip, temp_c, active, dropped_thermal, events)


def compute_live_set(active, dropped_thermal, dropped_dead):
    """Re-evaluate every node and return (live_ips, events:list[str])."""
    events = []
    live = []
    for ip in JETSON_IPS:
        rpc_up, temp_c = probe_node(ip)
        if decide_node(ip, rpc_up, temp_c, active, dropped_thermal, dropped_dead, events):
            live.append(ip)
    return live, events


def main():
    ap = argparse.ArgumentParser(description="Jetson cluster fault-tolerant RPC watchdog")
    ap.add_argument("--once", action="store_true", help="single pass, print live set and exit")
    ap.add_argument("--model", default="C:\\Models\\Qwen2.5-72B-Instruct-IQ3_XS.gguf", help="model path for invocation hint")
    ap.add_argument("--prompt", default="Hello, cluster.", help="prompt for invocation hint")
    args = ap.parse_args()

    active = set(JETSON_IPS)
    dropped_thermal = set()
    dropped_dead = set()

    if args.once:
        live, _ = compute_live_set(active, dropped_thermal, dropped_dead)
        print(f"LIVE NODES ({len(live)}/{len(JETSON_IPS)}): {rpc_string(live)}")
        return

    print(f"[WATCHDOG] Monitoring {len(JETSON_IPS)} nodes, RPC port {PORT}, "
          f"thermal WARN={THERMAL_WARN_C:.0f}C rejoin<{THERMAL_REJOIN_C:.0f}C")
    print(f"[WATCHDOG] Initial live set: {rpc_string(sorted(active))}")
    try:
        while True:
            # MAINTENANCE STAND-DOWN: when an OS shutdown / power action is in
            # progress, the dashboard flips cluster mode to 'maintenance'. The
            # watchdog must NOT re-slice or re-admit nodes during that window —
            # doing so would fight the shutdown and spam false fault events.
            if get_cluster_mode() == CLUSTER_MODE_MAINTENANCE:
                print("[WATCHDOG] MAINTENANCE mode — standing down (no re-slice / "
                      "no re-admit). Nodes may be intentionally down.")
                time.sleep(PROBE_INTERVAL_SEC)
                continue
            live, events = compute_live_set(active, dropped_thermal, dropped_dead)
            for e in events:
                print(e)
            if events:
                print(f"[WATCHDOG] NEW LIVE SET ({len(live)} nodes): {rpc_string(live)}")
                print(f"[WATCHDOG] Re-launch host with: llama-cli.exe -m {args.model} "
                      f"--flash-attn --rpc {rpc_string(live)} -p \"{args.prompt}\"")
            if len(live) == 0:
                print("[WATCHDOG] !! ALL NODES DOWN — cluster unavailable, halt host generation !!")
            time.sleep(PROBE_INTERVAL_SEC)
    except KeyboardInterrupt:
        print("\n[WATCHDOG] stopped.")


if __name__ == "__main__":
    main()
