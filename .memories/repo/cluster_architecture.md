# Cluster Architecture Facts (verified 2026-07-09)

## rpc-server binary (CANONICAL)
- Built binary is `rpc-server` (NO `llama-` prefix). Lives at `/home/jetson/llama.cpp/build/bin/rpc-server`.
- **This build REJECTS `--mlock`** ("error: unknown argument: --mlock"). Memory locking is provided instead by `mlockall_wrapper` (setuid-root wrapper that calls mlockall() then execv's ./rpc-server). Launch via the wrapper, NOT via `--mlock`.
- Correct launch: `cd <bindir> && setsid nohup ./mlockall_wrapper --host 0.0.0.0 --port 50052 --mem 3600 < /dev/null > log 2>&1 &`
- Flags are `--host`/`--port`/`--mem` (NOT `-H`/`-p`/`-m`).

## Bootloader CMA (APPLIED 2026-07-09)
- `cma=512M coherent_pool=64M alloc_as_vram=1` now in `/boot/extlinux/extlinux.conf` APPEND line on node 150.
- Verified: `dmesg` shows `cma: Reserved 512 MiB`. Reduces UMA fragmentation/OOM under load.
- Backup at `/boot/extlinux/extlinux.conf.bak-preCMA`.

## Services (node 150, golden image)
- `jetson-maxperf.service` + `cluster-init.service` were MISSING despite Phase 6 claiming enable — recreated + enabled 2026-07-09. They survive reboot (verified).
- `phase3b_disk_expand.service` (ConditionFirstBoot=yes) baked for cloned nodes.

## Health gate
- `code/phase8b_health_gate.sh` = deep pre-clone gate (8 checks, exit 1 on any FAIL). Wired into `phase9_cloning.sh` BEFORE 9b (abort clone on FAIL) and re-run per cloned node in 9d.
- Baseline run on node 150: 0 FAIL after service fix.

## Fault tolerance
- `code/cluster_watchdog.py` = node-drop re-slice + thermal actuation (drops hottest node at >=80C, re-admits <70C). Wired as `watchdog` mode in `cluster_deploy.py`.
- `cluster_deploy.py` launch uses `ssh -f` (non-blocking) + `setsid`; terminate uses `pkill -f '[r]pc-server'` (bracket trick avoids self-match hang).

## Cluster state (2026-07-09)
- Only node 150 (Nano Zero, template) is powered on. Workers 1-10 (151-160) are OFF / not yet flashed.
- Node 150 daemon confirmed listening on 50052 via wrapper.
