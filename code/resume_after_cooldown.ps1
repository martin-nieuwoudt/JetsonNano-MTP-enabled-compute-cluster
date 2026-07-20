#!/usr/bin/env powershell
# resume_after_cooldown.ps1 — Resume a model download after a thermal/network cooldown.
# Supersedes the old Qwen-specific resume script. Now registry-driven: pass -Model <key>.
#
# What it does:
#   1. Deletes any corrupted/partial final GGUF on node0 (keeps clean part.* there).
#   2. Relaunches the PC fetch DETACHED (resumes from existing part.* via dl_generic_model.py).
#   3. Logs a resume summary.
#
# Usage:
#   .\resume_after_cooldown.ps1 -Model qwen2.5-72b-iq3_m

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Model
)

$ErrorActionPreference = "Continue"
$CodeDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

# Resolve node0 path from the single source of truth.
$py = @"
import sys, os, json
sys.path.insert(0, r'$CodeDir')
import mcp.cluster_config as cfg
m = cfg.model_entry(r'$Model')
print(json.dumps({"local": m["local"], "node_dir": cfg.MODEL_DIR_ON_NODE0,
                  "node_ip": cfg.MODEL_NODE_IP, "ssh_user": cfg.SSH_USER}))
"@
$info = python -c $py | ConvertFrom-Json
$node = "$($info.ssh_user)@$($info.node_ip)"

# 1. Delete corrupted final file on node0 (keep clean part.* there).
ssh -o BatchMode=yes -o ConnectTimeout=15 $node "cd $($info.node_dir) && rm -f $(Split-Path -Leaf $info.local) && echo node0 garbage removed"

# 2. Relaunch PC fetch detached (resumes from existing part.*).
Start-Process -WindowStyle Hidden -FilePath "python" `
  -ArgumentList "$CodeDir\model_sync.py", "download", $Model `
  -RedirectStandardOutput "C:\Models\sync_model.log" `
  -RedirectStandardError "C:\Models\sync_model.err"

Start-Sleep -Seconds 20
$procs = (Get-Process -Name python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match 'model_sync.py' }).Count
$b = (Get-ChildItem "C:\Models\part.*" -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
$msg = "$ts RESUMED after cooldown | model=$Model | procs=$procs | parts=$([math]::Round($b/1GB,2)) GB"
Add-Content -Path "C:\Models\cooldown_resume.log" -Value $msg
Write-Output $msg
