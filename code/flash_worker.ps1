<#
.SYNOPSIS
    Prepare a Jetson worker image with per-worker identity, then wait for the
    (human-flashed) board to come up and verify it registers as an RPC worker.

.DESCRIPTION
    Deployment helper for nodes 1..10. It does NOT launch any flashing tool
    (Rufus / balenaEtcher / etc.) — the human does the physical write. The
    script:
      1. prepare_worker_image.ps1 bakes hostname + static IP into a per-worker
         copy of Jetson_Worker_Baseline.img (offline, via WSL loop mount).
      2. Prints the prepared image path and PAUSES, giving you time to flash
         the card with whatever tool you use and power the board on.
      3. Once the board responds to ping, verifies:
            - hostname == nanoNN
            - static IP == 192.168.50.NN/24
            - rpc-server LISTENING on 50052 (the cluster "join" signal)
            - node0 (.150) can reach the worker on 50052

    Identity mapping comes from code/mcp/cluster_config.py:
    .151=nano01 ... .160=nano10. Do NOT use this for node0 (.150 / nano00).

.PARAMETER WorkerNumber
    Worker index 1..10.

.PARAMETER BaselineImage
    Path to the pristine shrunk baseline image.

.PARAMETER SkipPrepare
    Reuse an already-prepared Jetson_Worker_nanoNN.img instead of rebuilding it.

.PARAMETER PauseSeconds
    How long to wait (after printing the image path) for you to flash + power
    on before the script starts polling for the board. Default 300.

.PARAMETER WaitSeconds
    How long to poll for the worker to respond to ping after the pause. Default 600.

.PARAMETER PollSeconds
    Poll interval. Default 5.

.EXAMPLE
    .\flash_worker.ps1 -WorkerNumber 7
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateRange(1,10)]
    [int]$WorkerNumber,

    [string]$BaselineImage = "C:\Users\marti\Desktop\Cluster\Jetson_Worker_Baseline.img",

    [switch]$SkipPrepare,

    [int]$PauseSeconds = 300,
    [int]$WaitSeconds = 600,
    [int]$PollSeconds = 5
)

$ErrorActionPreference = "Stop"
$ClusterDir = Split-Path $MyInvocation.MyCommand.Path -Parent
$ssh = "C:\Windows\System32\OpenSSH\ssh.exe"
$key = "C:\Users\marti\.ssh\id_ed25519"

$ipLast = 150 + $WorkerNumber
$ip     = "192.168.50.$ipLast"
$name   = "nano{0:00}" -f $WorkerNumber
$preparedImg = Join-Path (Split-Path $BaselineImage -Parent) ("Jetson_Worker_{0}.img" -f $name)

Write-Host "=== flash_worker : worker #$WorkerNumber ($name @ $ip) ==="

# --- 1. prepare per-worker image ------------------------------------------
if (-not $SkipPrepare) {
    $prep = Join-Path $ClusterDir "prepare_worker_image.ps1"
    Write-Host "Step 1/3: baking identity into $preparedImg ..."
    & pwsh -ExecutionPolicy Bypass -File $prep -WorkerNumber $WorkerNumber -BaselineImage $BaselineImage
    if (-not (Test-Path $preparedImg)) { throw "prepare step did not produce $preparedImg" }
} else {
    if (-not (Test-Path $preparedImg)) { throw "SkipPrepare set but $preparedImg missing" }
    Write-Host "Step 1/3: reusing existing $preparedImg"
}

# --- 2. PAUSE for the human to flash + power on (NO tool launched) ---------
Write-Host ""
Write-Host "Step 2/3: image ready. Flash it yourself with your tool of choice:"
Write-Host "  IMAGE : $preparedImg"
Write-Host "  TARGET: SD card for $name"
Write-Host "  Then plug the card into $name and power it on."
Write-Host "  (No flashing tool will be launched by this script.)"
Write-Host ""
Write-Host "Waiting up to $PauseSeconds s for you to flash + boot $name ..."
$ready = $false
for ($i = 0; $i -lt $PauseSeconds; $i += $PollSeconds) {
    if (Test-Connection -ComputerName $ip -Count 1 -Quiet -ErrorAction SilentlyContinue) {
        $ready = $true; break
    }
    Write-Host "  ... waiting for $name to appear on network ($i s elapsed)"
    Start-Sleep -Seconds $PollSeconds
}
if (-not $ready) {
    Write-Host "Worker did not respond to ping within $PauseSeconds s."
    Write-Host "Flash the card, power on $name, then re-run with -SkipPrepare."
    exit 1
}
Write-Host "  $name responded to ping."

# --- 3. verify boot + RPC registration -------------------------------------
Write-Host ""
Write-Host "Step 3/3: verifying boot + RPC registration on $name ..."
$sshArgs = @("-i", $key, "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=20", "jetson@$ip")
$probe = 'echo "HOST=$(hostname)"; echo "IP=$(ip -4 addr show eth0 | grep -oP "inet \K[\d./]+")"; if ss -ltn 2>/dev/null | grep -q 50052; then echo "RPC=LISTENING"; else echo "RPC=DOWN"; fi'
$out = & $ssh @sshArgs $probe 2>$null
$out | ForEach-Object { Write-Host "  $_" }

$hostOk = ($out -join "`n") -match "HOST=$name"
$ipOk   = ($out -join "`n") -match [regex]::Escape("IP=$ip/24")
$rpcOk  = ($out -join "`n") -match "RPC=LISTENING"

# node0 -> worker reachability (the actual cluster join signal)
$n0 = & $ssh -i $key -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o LogLevel=ERROR -o ConnectTimeout=20 "jetson@192.168.50.150" "timeout 4 bash -c '</dev/tcp/$ip/50052' && echo WORKER_50052_OPEN || echo WORKER_50052_CLOSED" 2>$null
$n0 | ForEach-Object { Write-Host "  node0->${ip}: $_" }
$joinOk = ($n0 -join "`n") -match "WORKER_50052_OPEN"

Write-Host ""
if ($hostOk -and $ipOk -and $rpcOk -and $joinOk) {
    Write-Host "RESULT: PASS — $name ($ip) booted, correctly identified, rpc-server listening, node0 can reach it on 50052."
    Write-Host "Worker #$WorkerNumber is deployed and joined the cluster."
} else {
    Write-Host "RESULT: PARTIAL/FAIL"
    Write-Host "  hostname correct : $hostOk"
    Write-Host "  static IP correct: $ipOk"
    Write-Host "  rpc-server       : $rpcOk"
    Write-Host "  node0 reachable  : $joinOk"
    Write-Host "Re-run with -SkipPrepare after fixing, or investigate manually."
    exit 1
}
