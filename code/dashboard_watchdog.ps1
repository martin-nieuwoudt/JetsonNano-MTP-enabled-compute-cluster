<#
.SYNOPSIS
    Watchdog for the Jetson Cluster Dashboard (cluster_telemetry.py web mode).
    Monitors port 9090 and auto-restarts if the process dies.

.DESCRIPTION
    - Checks /health endpoint every 10 seconds.
    - If unreachable, kills any stale pythonw on :9090 and restarts fresh.
    - Logs to dashboard_watchdog.log in the code directory.
    - Designed to run as a Windows Scheduled Task (at logon, hidden window).

.NOTES
    Run manually for testing:
      powershell -NoProfile -ExecutionPolicy Bypass -File dashboard_watchdog.ps1

    Register as scheduled task (run once as admin):
      Register-ScheduledTask -Xml (Get-Content dashboard_watchdog_task.xml | Out-String) -TaskName "JetsonDashboardWatchdog"
#>

[CmdletBinding()]
param(
    [string]$DashboardPort = "9090",
    [string]$PythonW = "pythonw",
    [string]$ScriptDir = "C:\Users\marti\Desktop\Cluster\code",
    [string]$ScriptName = "cluster_telemetry.py",
    [int]$CheckIntervalSec = 10,
    [int]$RestartGraceSec = 5,
    [int]$MaxRestartsPerMinute = 3,
    [int]$HealthTimeoutMs = 5000
)

$LogDir = $ScriptDir
$LogFile = Join-Path $LogDir "dashboard_watchdog.log"
$restartTimes = [System.Collections.Queue]::new($MaxRestartsPerMinute)

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$timestamp] $Message"
    Add-Content -Path $LogFile -Value $line -ErrorAction SilentlyContinue
}

function Kill-PortOwner {
    param([string]$Port)
    try {
        $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
        if ($conns) {
            foreach ($conn in $conns) {
                $pid = $conn.OwningProcess
                if ($pid -and $pid -gt 0) {
                    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                    Write-Log "Killed stale process $pid on port $Port"
                }
            }
        }
    } catch {
        Write-Log "Kill-PortOwner error: $_"
    }
}

function Start-Dashboard {
    try {
        $proc = Start-Process -FilePath $PythonW `
            -ArgumentList "$ScriptName web" `
            -WorkingDirectory $ScriptDir `
            -WindowStyle Hidden `
            -PassThru -ErrorAction Stop
        Write-Log "Started dashboard (PID $($proc.Id))"
        return $true
    } catch {
        Write-Log "Failed to start dashboard: $_"
        return $false
    }
}

function Test-Health {
    try {
        $url = "http://127.0.0.1:${DashboardPort}/health"
        $resp = Invoke-WebRequest -Uri $url -TimeoutSec 5 -UseBasicParsing -ErrorAction Stop
        return ($resp.StatusCode -eq 200)
    } catch {
        return $false
    }
}

Write-Log "=== Dashboard Watchdog started ==="
Write-Log "Port: $DashboardPort | Script: $ScriptDir\$ScriptName | Interval: ${CheckIntervalSec}s"

while ($true) {
    $healthy = Test-Health

    if (-not $healthy) {
        Write-Log "HEALTH CHECK FAILED on port $DashboardPort - attempting restart"

        # Rate-limit restarts
        $now = [DateTimeOffset]::Now
        $restartTimes.Enqueue($now)
        if ($restartTimes.Count -gt $MaxRestartsPerMinute) {
            $restartTimes.Dequeue()
        }
        $oneMinAgo = $now.AddMinutes(-1)
        $recentRestarts = ($restartTimes | Where-Object { $_ -gt $oneMinAgo }).Count

        if ($recentRestarts -gt $MaxRestartsPerMinute) {
            Write-Log "Restart rate limit hit ($recentRestarts in last min) - backing off"
            Start-Sleep -Seconds 30
            continue
        }

        # Kill stale process and restart
        Kill-PortOwner -Port $DashboardPort
        Start-Sleep -Seconds 1

        if (Start-Dashboard) {
            # Wait for it to come up
            Start-Sleep -Seconds $RestartGraceSec
            $cameUp = Test-Health
            if ($cameUp) {
                Write-Log "Dashboard restarted successfully"
            } else {
                Write-Log "Dashboard may not have started properly - will retry next cycle"
            }
        }
    }

    Start-Sleep -Seconds $CheckIntervalSec
}
