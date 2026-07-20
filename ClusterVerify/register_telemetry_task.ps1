# Register a Windows Scheduled Task that launches the cluster telemetry
# dashboard at user logon (headless, no console window).
# Run elevated. Idempotent: deletes + recreates the task if it exists.

$TaskName = "ClusterTelemetryDashboard"
$Py       = "C:\Python314\pythonw.exe"
$Script   = "C:\Users\marti\Desktop\Cluster\code\cluster_telemetry.py"
$StartDir = "C:\Users\marti\Desktop\Cluster\code"

# Remove any prior instance
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }

$Arg    = "`"$Script`" web"   # quoted path + mode
$action = New-ScheduledTaskAction -Execute $Py -Argument $Arg -WorkingDirectory $StartDir

$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
                                         -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) `
                                         -ExecutionTimeLimit (New-TimeSpan -Days 3650)

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
                       -Settings $settings -Description "Jetson cluster telemetry dashboard (http://localhost:9090)" `
                       -User "$env:USERDOMAIN\$env:USERNAME" -RunLevel Limited

Write-Host "Registered task: $TaskName"
$reg = Get-ScheduledTask -TaskName $TaskName
Write-Host ("State: " + $reg.State)
