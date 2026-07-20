$ErrorActionPreference = 'Stop'
$img = 'C:\Users\marti\Desktop\Cluster\Jetson_Worker_Node1_FullBackup_2026-07-12.img'
$log = 'C:\Users\marti\Desktop\Cluster\backup_progress.log'
$dd  = 'C:\Program Files\Git\usr\bin\dd.exe'

"=== backup started $(Get-Date) (conv=noerror,sync) ===" | Out-File -Append $log
if (Test-Path $img) { Remove-Item $img -Force; "removed partial image" | Out-File -Append $log }

# Read the ENTIRE raw SD card (Disk 1 = 63.8 GB) to a raw .img. No pigz.
# conv=noerror,sync: survive transient reader errors (write zeros for a bad block, keep going)
# direct 2>> redirection (no pipe) so progress is flushed live to the log
& $dd if=\\.\PhysicalDrive1 of=$img bs=1M conv=noerror,sync iflag=fullblock status=progress 2>> $log
"DD_DONE_EXIT=$LASTEXITCODE" | Out-File -Append $log
"=== finished $(Get-Date) ===" | Out-File -Append $log
