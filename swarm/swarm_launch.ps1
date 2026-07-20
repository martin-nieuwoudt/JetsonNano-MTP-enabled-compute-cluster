# swarm_launch.ps1
# GENERAL swarm launcher. Deploy a swarm from chat for ANY problem, on the
# EXACT models you name. Every (model x target) pair runs as its own agent job
# in parallel. Built for the OpenRouter free/paid model pool.
#
# Usage (from chat, I run this for you):
#   .\swarm_launch.ps1 -Brief "briefs\cuda_cpp17_to_cpp14.md" `
#       -Models "nvidia/nemotron-3-super-120b-a12b:free","tencent/hy3:free" `
#       -Targets "/home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda/common.cuh" `
#       -Remote "jetson@192.168.50.150"
# Paths are resolved relative to this script's folder, so the whole swarm/
# folder can be copied anywhere and used there.
#
# Parameters:
#   -Brief    : path to a markdown brief file (the problem statement / instructions)
#   -Models   : comma-separated OpenRouter model IDs (you choose exactly which)
#   -Targets  : comma-separated file paths. If -Remote is set, these are REMOTE
#               paths pulled via scp and pushed back. If -Remote is omitted, they
#               are LOCAL paths (edited in place).
#   -Remote   : optional "user@host" for remote targets (scp pull/push)
#   -MaxRetry : retries on HTTP 429 (rate limit) with backoff (default 4)
#   -Timeout  : per-call timeout seconds (default 300)
#
# Output: each agent writes its result next to the target as "<name>.swarm.<model-slug>"
# and, for remote targets, pushes the patched file back to the host.

param(
    [Parameter(Mandatory=$true)]  [string]   $Brief,
    [Parameter(Mandatory=$true)]  [string[]] $Models,
    [string[]] $Targets = @(),
    [string]   $Remote = "",
    [int]      $MaxRetry = 4,
    [int]      $Timeout = 300
)

if (-not $env:OPENROUTER_API_KEY) {
    Write-Error "Set `$env:OPENROUTER_API_KEY first (in your terminal, not chat)."
    exit 1
}
# Resolve the brief relative to this script's folder so the swarm folder is portable.
$briefPath = if ([System.IO.Path]::IsPathRooted($Brief)) { $Brief } else { Join-Path $PSScriptRoot $Brief }
if (-not (Test-Path $briefPath)) { Write-Error "Brief not found: $briefPath"; exit 1 }

$BRIEF_TEXT = Get-Content $briefPath -Raw -Encoding UTF8
$WORK = Join-Path $PSScriptRoot "_work"
New-Item -ItemType Directory -Force -Path $WORK | Out-Null
$wslWork = "/mnt/c/" + ($WORK -replace '^C:\\','' -replace '\\','/')

function Slug([string]$m) { return ($m -replace '[^a-zA-Z0-9]','-') }

# Build the job list: one job per (model, target) pair.
# If no targets given, it's a consultation swarm: one job per model, brief only.
$jobs = @()
if ($Targets.Count -eq 0) {
    foreach ($model in $Models) {
        $jobs += [pscustomobject]@{ model = $model; target = "" }
    }
    Write-Host "Swarm: consultation mode, $($Models.Count) model(s) on the brief."
} else {
    foreach ($model in $Models) {
        foreach ($target in $Targets) {
            $jobs += [pscustomobject]@{ model = $model; target = $target }
        }
    }
    Write-Host "Swarm: $($Models.Count) model(s) x $($Targets.Count) target(s) = $($jobs.Count) agent job(s)."
}

# ---- Fan out all jobs in parallel ----
$results = $jobs | ForEach-Object -Parallel {
    $Model = $_.model; $Target = $_.target
    $slug = ($Model -replace '[^a-zA-Z0-9]','-')

    # ---- Acquire source (skip if no target = consultation mode) ----
    if (-not $Target) {
        $code = ""
        $name = "consultation"
    } else {
        $name = Split-Path $Target -Leaf
        if ($using:Remote) {
            & wsl -d Ubuntu -e bash -c "scp -o BatchMode=yes '$($using:Remote)`:$Target' '$($using:wslWork)/$name'" 2>&1 | Out-Null
            if (-not (Test-Path "$($using:WORK)\$name")) { return "ERROR [$Model] [$name]: pull failed from $($using:Remote)" }
            $code = Get-Content "$($using:WORK)\$name" -Raw -Encoding UTF8
        } else {
            if (-not (Test-Path $Target)) { return "ERROR [$Model] [$name]: local file not found" }
            $code = Get-Content $Target -Raw -Encoding UTF8
        }
    }

    # ---- Call model with retry/backoff on 429 ----
    $body = @{
        model = $Model
        messages = @(
            @{ role = "system"; content = $using:BRIEF_TEXT },
            @{ role = "user";   content = $(if ($code) { "Work on this file:`n`n$code" } else { "Address the problem described above." }) }
        )
        temperature = 0
    } | ConvertTo-Json -Depth 5

    $attempt = 0; $patched = $null
    while ($attempt -le $using:MaxRetry) {
        try {
            $resp = Invoke-RestMethod -Uri "https://openrouter.ai/api/v1/chat/completions" `
                -Method Post -ContentType "application/json" `
                -Headers @{ Authorization = "Bearer $env:OPENROUTER_API_KEY" } `
                -Body $body -TimeoutSec $using:Timeout
            $patched = $resp.choices[0].message.content
            break
        } catch {
            $msg = $_.ToString()
            if ($msg -match '429' -or $msg -match 'rate-limited') {
                $attempt++
                if ($attempt -gt $using:MaxRetry) { return "ERROR [$Model] [$name]: rate-limited after $($using:MaxRetry) retries" }
                Start-Sleep -Seconds (16 * $attempt)
                continue
            }
            return "ERROR [$Model] [$name]: $msg"
        }
    }

    # strip accidental fences
    $patched = $patched -replace '^```[a-zA-Z]*\s*','' -replace '```\s*$',''

    # ---- Write result ----
    if (-not $Target) {
        $out = Join-Path $using:WORK "$slug.txt"
        Set-Content $out $patched -Encoding UTF8
        return "OK [$Model] [consultation] -> wrote $out"
    } elseif ($using:Remote) {
        Set-Content "$($using:WORK)\$name" $patched -Encoding UTF8
        & wsl -d Ubuntu -e bash -c "scp -o BatchMode=yes '$($using:wslWork)/$name' '$($using:Remote)`:$Target'" 2>&1 | Out-Null
        return "OK [$Model] [$name] -> patched, pushed to $($using:Remote)"
    } else {
        $out = Join-Path (Split-Path $Target) "$name.swarm.$slug"
        Set-Content $out $patched -Encoding UTF8
        return "OK [$Model] [$name] -> wrote $out"
    }
} -ThrottleLimit 8

$results | ForEach-Object { $_ }
