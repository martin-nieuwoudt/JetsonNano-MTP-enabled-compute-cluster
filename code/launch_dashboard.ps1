# launch_dashboard.ps1
# ---------------------------------------------------------------------------
# Persistent launcher for the Jetson cluster telemetry dashboard.
# Guarantees the dashboard always runs the CURRENT code on port 9090:
# any process already bound to 9090 (e.g. a stale pre-fix server from a
# previous session) is killed first, so a relaunch can never silently fail
# to bind the way it did on 2026-07-13/14.
#
# Intended to be invoked by the "ClusterTelemetryDashboard" scheduled task
# (trigger: AtLogOn, run level: Highest) so it survives reboots.
# ---------------------------------------------------------------------------
$ErrorActionPreference = 'SilentlyContinue'

$PORT    = 9090
$PY      = "C:\Python314\pythonw.exe"
$SCRIPT  = "C:\Users\marti\Desktop\Cluster\code\cluster_telemetry.py"
$WORKDIR = "C:\Users\marti\Desktop\Cluster\code"

# 1) Kill anything already listening on 9090 (stale server, orphaned pythonw).
$conns = Get-NetTCPConnection -LocalPort $PORT -State Listen -ErrorAction SilentlyContinue
foreach ($c in $conns) {
    $owner = $c.OwningProcess
    if ($owner -and $owner -ne $PID) {
        try { Stop-Process -Id $owner -Force } catch { }
    }
}
Start-Sleep -Seconds 1

# 2) Launch the dashboard headless. pythonw detaches from the console so the
#    scheduled task returns immediately and the server keeps running.
Start-Process -FilePath $PY `
    -ArgumentList "`"$SCRIPT`" web" `
    -WorkingDirectory $WORKDIR `
    -WindowStyle Hidden
