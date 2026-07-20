$svc = New-Object -ComObject Schedule.Service
$svc.Connect()
$folder = $svc.GetFolder("\")
$results = @()
foreach ($name in @("ClusterSSD-Z-Reconnect", "ClusterTelemetryDashboard")) {
    $task = $folder.GetTask($name)
    $def = $task.Definition
    $def.Settings.Hidden = $true
    $folder.RegisterTaskDefinition($name, $def, 4, $null, $null, $def.Principal.LogonType)
    $verify = $folder.GetTask($name).Definition.Settings.Hidden
    $results += "$name -> Hidden=$verify"
}
$results | Out-File -FilePath "C:\Users\marti\Desktop\Cluster\code\hide_tasks_result.txt" -Encoding utf8
