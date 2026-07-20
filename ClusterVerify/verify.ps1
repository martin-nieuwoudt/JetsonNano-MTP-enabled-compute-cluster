$log = "C:\ClusterVerify\log.txt"
"$(Get-Date) START elevated verify (usbipd path)" | Out-File -Append $log
try {
    "$(Get-Date) ensuring WSL Ubuntu running" | Out-File -Append $log
    wsl -d Ubuntu -u root -e true 2>&1 | Out-File -Append $log
    Start-Sleep -Seconds 2
    "$(Get-Date) usbipd attach 2-2 -> Ubuntu" | Out-File -Append $log
    usbipd attach --busid 2-2 --wsl 2>&1 | Out-File -Append $log
    Start-Sleep -Seconds 5
    $r = wsl -d Ubuntu -u root -e bash -c "for i in 1 2 3 4 5 6 7 8 9 10; do [ -b /dev/sde1 ] && break; sleep 1; done; echo DEV_CHECK:; ls -l /dev/sde1 2>&1; mkdir -p /mnt/card; mount -o ro /dev/sde1 /mnt/card; echo '=== SSH SYMLINK ==='; ls -l /mnt/card/etc/systemd/system/multi-user.target.wants/ssh.service 2>&1; echo '=== HOST KEYS (expect none) ==='; ls /mnt/card/etc/ssh/ssh_host_* 2>&1; umount /mnt/card; echo DONE" 2>&1
    "$(Get-Date) RESULT:`n$r" | Out-File -Append $log
    "$(Get-Date) usbipd detach 2-2" | Out-File -Append $log
    usbipd detach --busid 2-2 2>&1 | Out-File -Append $log
} catch {
    "$(Get-Date) ERROR: $_" | Out-File -Append $log
}
"$(Get-Date) END" | Out-File -Append $log
