$log = "C:\ClusterVerify\nopw_log.txt"
"$(Get-Date) START offline no-password setup" | Out-File -Append $log
try {
    "$(Get-Date) ensure WSL running" | Out-File -Append $log
    wsl -d Ubuntu -u root -e true 2>&1 | Out-File -Append $log
    Start-Sleep -Seconds 2
    "$(Get-Date) usbipd attach 2-2" | Out-File -Append $log
    usbipd attach --busid 2-2 --wsl 2>&1 | Out-File -Append $log
    Start-Sleep -Seconds 5
    $r = wsl -d Ubuntu -u root -e bash /mnt/c/ClusterVerify/nopw.sh 2>&1
    "$(Get-Date) RESULT:`n$r" | Out-File -Append $log
    "$(Get-Date) usbipd detach 2-2" | Out-File -Append $log
    usbipd detach --busid 2-2 2>&1 | Out-File -Append $log
} catch {
    "$(Get-Date) ERROR: $_" | Out-File -Append $log
}
"$(Get-Date) END" | Out-File -Append $log
