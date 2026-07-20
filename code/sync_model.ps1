#!/usr/bin/env powershell
# sync_model.ps1 — Unified model sync tool (PC side). Supersedes:
#   scp_qwen_to_node0.ps1, verify_qwen_node0.ps1, download_orchestrator.ps1,
#   resume_qwen_after_cooldown.ps1
#
# Architecture (single source of truth): ALL GGUFs live on Nano Zero's USB SSD and
# are NFS-exported to workers. The PC is the SOURCE of truth for model files; the
# default direction is PC -> node0 (push). Node0 -> PC is supported only as an
# explicit recovery op (e.g. re-fetch a model that lives only on a node).
#
# Usage:
#   .\sync_model.ps1 -Model <key> [-Direction PCtoNode0|Node0toPC] [-VerifyOnly]
#   .\sync_model.ps1 -Model qwen2.5-72b-iq3_m                 # push + verify
#   .\sync_model.ps1 -Model qwen2.5-72b-iq3_m -VerifyOnly     # compare only, no copy
#   .\sync_model.ps1 -Model qwen2.5-72b-iq3_m -Direction Node0toPC   # recover to PC
#
# Model keys/paths are resolved from mcp.cluster_config (via model_sync.py) — never
# hardcoded here. Run from the code/ directory (or set $CodeDir).

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Model,

    [ValidateSet("PCtoNode0", "Node0toPC")]
    [string]$Direction = "PCtoNode0",

    [switch]$VerifyOnly
)

$ErrorActionPreference = "Stop"
$CodeDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$log = "C:\Models\sync_model.log"

function Log($m) {
    $t = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "$t  $m" | Tee-Object -FilePath $log -Append
}

# --- Resolve model paths from the single source of truth (cluster_config via model_sync.py)
function Resolve-Model {
    param([string]$key)
    $py = @"
import sys, os, json
sys.path.insert(0, r'$CodeDir')
import mcp.cluster_config as cfg
m = cfg.model_entry(r'$key')
print(json.dumps({"local": m["local"], "hf_url": m["hf_url"],
                  "node_dir": cfg.MODEL_DIR_ON_NODE0, "node_ip": cfg.MODEL_NODE_IP,
                  "ssh_user": cfg.SSH_USER}))
"@
    $info = python -c $py
    return ($info | ConvertFrom-Json)
}

try {
    $m = Resolve-Model -key $Model
} catch {
    Log "UNKNOWN MODEL KEY: $Model"; Write-Error "Unknown model key: $Model"; exit 2
}

$pcFile   = $m.local
$nodeFile = "$($m.node_dir)/$(Split-Path -Leaf $pcFile)"
$node     = "$($m.ssh_user)@$($m.node_ip)"
$sidecar  = "$pcFile.sha256"

Log "=== sync_model $Model ($Direction) ==="
Log "PC file   = $pcFile"
Log "node0 file= $nodeFile"

# --- Verify-only or pre-check: compare sizes + sha256
function Verify {
    if (-not (Test-Path $pcFile)) { Log "PC file missing: $pcFile"; return $false }
    $pcSize = (Get-Item $pcFile).Length
    $nodeSize = (ssh -o ConnectTimeout=15 -o BatchMode=yes $node "stat -c '%s' $nodeFile" 2>&1)
    Log "PC size=$pcSize  node0 size=$nodeSize"
    if ($nodeSize -notmatch '^\d+$' -or [long]$nodeSize -ne $pcSize) {
        Log "SIZE MISMATCH"; return $false
    }
    Log "SIZE MATCH"
    # PC hash: prefer sidecar (canonical <basename>.gguf.sha256), else compute.
    if (Test-Path $sidecar) {
        $pcHash = (Get-Content $sidecar -Raw).Trim().Split()[0].ToUpper()
    } else {
        $pcHash = (Get-FileHash -Algorithm SHA256 $pcFile).Hash.ToUpper()
        Log "no sidecar; computed PC sha256"
    }
    Log "PC sha256  = $pcHash"
    $nodeHash = (ssh -o ConnectTimeout=15 -o BatchMode=yes $node "sha256sum $nodeFile" 2>&1)
    if ($nodeHash -notmatch '[0-9a-fA-F]{64}') {
        $nodeHash = (ssh -o ConnectTimeout=15 -o BatchMode=yes $node "openssl dgst -sha256 $nodeFile" 2>&1)
    }
    $nodeHashClean = ($nodeHash -replace '.*?([0-9a-fA-F]{64}).*', '$1').ToUpper()
    Log "node0 hash = $nodeHashClean"
    if ($nodeHashClean -eq $pcHash) { Log "SHA256 MATCH - VERIFIED OK"; return $true }
    Log "SHA256 MISMATCH"; return $false
}

if ($VerifyOnly) {
    $ok = Verify
    if ($ok) { Log "=== verify complete: OK ==="; exit 0 } else { Log "=== verify FAILED ==="; exit 1 }
}

# --- Copy
if ($Direction -eq "PCtoNode0") {
    if (-not (Test-Path $pcFile)) { Log "PC file missing: $pcFile (download first)"; exit 1 }
    ssh -o ConnectTimeout=15 -o BatchMode=yes $node "mkdir -p $($m.node_dir) && echo ready" 2>&1 | Out-Null
    Log "SCP PC -> node0 ..."
    scp -o ConnectTimeout=15 -o BatchMode=yes $pcFile "${node}:${nodeFile}" 2>&1
    if (Test-Path $sidecar) {
        scp -o ConnectTimeout=15 -o BatchMode=yes $sidecar "${node}:${nodeFile}.sha256" 2>&1
        Log "sidecar copied"
    }
} else {  # Node0toPC (recovery)
    Log "SCP node0 -> PC ..."
    scp -o ConnectTimeout=15 -o BatchMode=yes "${node}:${nodeFile}" $pcFile 2>&1
}

# --- Verify after copy
$ok = Verify
if ($ok) { Log "=== sync complete: OK ==="; exit 0 } else { Log "=== sync FAILED ==="; exit 1 }
