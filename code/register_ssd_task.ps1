$ErrorActionPreference = 'Stop'
$scriptPath = "c:\Users\marti\Desktop\Cluster\code\mount_ssd_z.ps1"
$action = New-ScheduledTaskAction -Execute "PowerShell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$scriptPath`""
$triggers = @(
    (New-ScheduledTaskTrigger -AtLogOn),
    (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 24855))
)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 2)
Register-ScheduledTask -TaskName "ClusterSSD-Z-Reconnect" -Action $action -Trigger $triggers -Settings $settings -Description "Auto-map node0 SSD (Z:) when the cluster is reachable" -Force
Write-Output "Registered: ClusterSSD-Z-Reconnect"
