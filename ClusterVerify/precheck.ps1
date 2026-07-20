$log = "C:\ClusterVerify\precheck_log.txt"
"$(Get-Date) START precheck" | Out-File -Append $log
try {
    wsl -d Ubuntu -u root -e true 2>&1 | Out-File -Append $log
    Start-Sleep -Seconds 2
    usbipd attach --busid 2-2 --wsl 2>&1 | Out-File -Append $log
    Start-Sleep -Seconds 5
    $r = wsl -d Ubuntu -u root -e bash /mnt/c/ClusterVerify/precheck.sh 2>&1
    "$(Get-Date) RESULT:`n$r" | Out-File -Append $log
    usbipd detach --busid 2-2 2>&1 | Out-File -Append $log
} catch {
    "$(Get-Date) ERROR: $_" | Out-File -Append $log
}
"$(Get-Date) END" | Out-File -Append $log
