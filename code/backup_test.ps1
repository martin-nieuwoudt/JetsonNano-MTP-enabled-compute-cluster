$ErrorActionPreference = 'Stop'
$dd = 'C:\Program Files\Git\usr\bin\dd.exe'
$log = 'C:\Users\marti\Desktop\Cluster\backup_test.log'
"=== 256MB read test $(Get-Date) ===" | Out-File -Append $log
$sw = [System.Diagnostics.Stopwatch]::StartNew()
& $dd if=\\.\PhysicalDrive1 of=/dev/null bs=4M count=64 status=progress 2>&1 | ForEach-Object { $_ | Out-File -Append $log }
$sw.Stop()
"elapsed_s=$($sw.Elapsed.TotalSeconds) exit=$LASTEXITCODE" | Out-File -Append $log
