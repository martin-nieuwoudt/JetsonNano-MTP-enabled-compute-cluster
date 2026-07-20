<#
.SYNOPSIS
    Wait for nano03 (192.168.50.153) to come up after the card is plugged in,
    then verify it joins the cluster as an RPC worker.

.DESCRIPTION
    The card Jetson_Worker_nano03.img is already flashed and "ready to plug".
    This script does NOT launch Rufus. It polls for the board to appear on the
    network, then verifies:
        - hostname == nano03
        - static IP == 192.168.50.153/24
        - rpc-server LISTENING on 50052 (cluster "join" signal)
        - node0 (.150) can reach the worker on 50052

    Identity mapping from code/mcp/cluster_config.py: .153 = nano03.
#>
[CmdletBinding()]
param(
    [int]$WaitSeconds = 600,
    [int]$PollSeconds = 5
)

$ErrorActionPreference = "Stop"
$ssh = "C:\Windows\System32\OpenSSH\ssh.exe"
$key = "C:\Users\marti\.ssh\id_ed25519"
$ip  = "192.168.50.153"
$name = "nano03"

Write-Host "=== verify_worker3 : waiting for $name ($ip) to come up (max ${WaitSeconds}s) ==="

$ready = $false
for ($i = 0; $i -lt $WaitSeconds; $i += $PollSeconds) {
    if (Test-Connection -ComputerName $ip -Count 1 -Quiet -ErrorAction SilentlyContinue) {
        $ready = $true
        Write-Host "  $name responded to ping after ~${i}s."
        break
    }
    Write-Host "  ... waiting ($i s elapsed)"
    Start-Sleep -Seconds $PollSeconds
}
if (-not $ready) {
    Write-Host "TIMEOUT: $name did not respond within $WaitSeconds s. Plug the card in / power on, then re-run."
    exit 1
}

# Give SSH a moment to be ready after first ping
Start-Sleep -Seconds 5

Write-Host ""
Write-Host "=== verifying boot + RPC registration on $name ==="
$sshArgs = @("-i", $key, "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=20", "jetson@$ip")
$probe = 'echo "HOST=$(hostname)"; IP=$(ip -4 addr show eth0 | grep -oP "inet \K[\d./]+"); if ss -ltn 2>/dev/null | grep -q 50052; then echo "RPC=LISTENING"; else echo "RPC=DOWN"; fi'
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
    Write-Host "Worker #3 (nano03) is deployed and joined the cluster."
} else {
    Write-Host "RESULT: PARTIAL/FAIL"
    Write-Host "  hostname correct : $hostOk"
    Write-Host "  static IP correct: $ipOk"
    Write-Host "  rpc-server       : $rpcOk"
    Write-Host "  node0 reachable  : $joinOk"
    Write-Host "Investigate manually or re-run after fixing."
    exit 1
}
