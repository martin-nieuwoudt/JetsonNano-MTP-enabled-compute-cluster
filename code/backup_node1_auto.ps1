$ErrorActionPreference = 'Stop'

$img = 'C:\Users\marti\Desktop\Cluster\Jetson_Worker_Node1_FullBackup_2026-07-12.img'
$log = 'C:\Users\marti\Desktop\Cluster\backup_progress.log'
$dd  = 'C:\Program Files\Git\usr\bin\dd.exe'

# --- auto-detect the 63.8 GB Jetson card by size (not hardcoded disk number) ---
$target = $null
foreach ($d in Get-Disk) {
    # Jetson 64GB card reports ~63.8 GB = 63864569856 bytes
    if ($d.Size -ge 60GB -and $d.Size -le 65GB) { $target = $d; break }
}
if (-not $target) {
    # fallback: this reader sometimes reports a blank Size via Get-Disk,
    # but BusType is reliable. There is exactly one USB disk (the reader).
    $usb = @(Get-Disk | Where-Object { $_.BusType -eq 'USB' })
    if ($usb.Count -eq 1) { $target = $usb[0] }
}
if (-not $target) {
    "ERROR: no ~64GB removable disk found. Disks present:" | Out-File -Append $log
    Get-Disk | Format-Table -AutoSize | Out-String | Out-File -Append $log
    throw "Jetson card not detected"
}
$drive = "\\.\PhysicalDrive$($target.Number)"
"detected Jetson card as $drive ($([math]::Round($target.Size/1GB,1)) GB)" | Out-File -Append $log

"=== backup started $(Get-Date) (auto-detect, conv=noerror,sync) ===" | Out-File -Append $log
if (Test-Path $img) { Remove-Item $img -Force; "removed partial image" | Out-File -Append $log }

# conv=noerror,sync: survive transient reader errors (write zeros for a bad block, keep going)
# direct 2>> redirection (no pipe) so progress is flushed live to the log
& $dd if=$drive of=$img bs=1M conv=noerror,sync iflag=fullblock status=progress 2>> $log

"DD_DONE_EXIT=$LASTEXITCODE" | Out-File -Append $log
"=== finished $(Get-Date) ===" | Out-File -Append $log
