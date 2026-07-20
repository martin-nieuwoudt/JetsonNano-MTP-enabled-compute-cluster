<#
  backup_node1_network.ps1
  FALLBACK to the flaky USB reader.
  Reads node1's SD card NATIVELY from inside node1 (no USB reader on the PC)
  and streams the raw image over SSH to this PC. No reader, no usbipd,
  no Windows \\.\PhysicalDrive lock.

  Prereqs for this path:
    - node1's card is back IN node1 (not the USB reader).
    - node1 is booted and reachable at its DHCP-reserved IP (192.168.50.151).
    - PC's id_ed25519 is authorized on node1 (set during Phase 3, inherited by workers).
    - node1 has passwordless sudo (set in Phase 4) so `sudo dd` doesn't prompt.
#>
$ErrorActionPreference = 'Stop'

$nodeIP  = '192.168.50.151'                                   # node1 worker (DHCP reservation)
$sshUser = 'jetson'
$key     = 'C:\Users\marti\.ssh\id_ed25519'
$img     = 'C:\Users\marti\Desktop\Cluster\Jetson_Worker_Node1_FullBackup_2026-07-12.img'
$log     = 'C:\Users\marti\Desktop\Cluster\backup_progress.log'
$nodeLog = 'C:\Users\marti\Desktop\Cluster\node1_dd_stderr.log'   # node1's dd stderr (read errors / record counts)

# resolve ssh.exe (prefer Windows OpenSSH, fall back to Git)
$ssh = 'C:\Windows\System32\OpenSSH\ssh.exe'
if (-not (Test-Path $ssh)) { $ssh = 'C:\Program Files\Git\usr\bin\ssh.exe' }
if (-not (Test-Path $ssh)) { throw 'ssh.exe not found on this PC' }

"=== NETWORK backup started $(Get-Date) (node1 $nodeIP -> PC over SSH) ===" | Out-File -Append $log
if (Test-Path $img) { Remove-Item $img -Force; "removed partial image" | Out-File -Append $log }

# node1 reads its OWN SD (/dev/mmcblk0) natively. dd stdout = image data only.
# We DO NOT discard stderr: node1's dd stderr (record counts + any read errors)
# is captured to $nodeLog so we can verify the backup is genuine (not zero-padded).
# The SSH channel carries stdout back to the PC, redirected to $img. Raw (no gzip):
# card is ~full, so compression buys nothing and would just load the Nano's slow ARM CPU.
# NOTE: conv=sync,noerror is a safety net only - if node1's reader were flaky we'd
# SEE the errors in $nodeLog. A clean run shows "0+0 records out" errors.
$remoteCmd = "sudo dd if=/dev/mmcblk0 bs=4M conv=sync,noerror 2>/tmp/node1_dd_stderr.log; echo EXITCODE=`$? >&2; cat /tmp/node1_dd_stderr.log >&2"

$job = Start-Process -FilePath $ssh -ArgumentList @(
    '-i', $key,
    '-o', 'StrictHostKeyChecking=no',
    '-o', 'UserKnownHostsFile=/dev/null',
    '-o', 'ConnectTimeout=15',
    '-o', 'ServerAliveInterval=30',
    "$sshUser@$nodeIP", $remoteCmd
) -RedirectStandardOutput $img -RedirectStandardError $nodeLog -NoNewWindow -PassThru

"launched ssh pid $($job.Id)" | Out-File -Append $log

# monitor file growth on the PC side
$last = 0
while (-not $job.HasExited) {
    Start-Sleep -Seconds 15
    if (Test-Path $img) {
        $sz   = (Get-Item $img).Length
        $rate = [math]::Round(($sz - $last) / 1MB / 15, 1)
        $eta  = if ($sz -gt 0) { [math]::Round((63864569856 - $sz) / ($sz - $last) * 15 / 3600, 2) } else { 'n/a' }
        "$(Get-Date -Format HH:mm:ss) size=$([math]::Round($sz/1GB,2))GB rate=${rate}MB/s eta_h=$eta" | Out-File -Append $log
        $last = $sz
    }
}
"DD_DONE_EXIT=$($job.ExitCode)" | Out-File -Append $log

# --- integrity check ---
$final = if (Test-Path $img) { (Get-Item $img).Length } else { 0 }
$expected = 63864569856
"final size = $final bytes (expected $expected)" | Out-File -Append $log
if ($final -ne $expected) {
    "WARN: size mismatch - image may be incomplete/corrupt" | Out-File -Append $log
} else {
    "SIZE_OK" | Out-File -Append $log
}
# scan for all-zero 4MB blocks (would indicate a failed read that got zero-padded)
$z = 0; $total = 0
$stream = [System.IO.File]::OpenRead($img)
$buf = New-Object byte[] (4MB)
try {
    while (($n = $stream.Read($buf, 0, $buf.Length)) -gt 0) {
        $total++
        $allZero = $true
        for ($i = 0; $i -lt $n; $i += 4096) {  # sample every 4KB page
            if ($buf[$i] -ne 0) { $allZero = $false; break }
        }
        if ($allZero) { $z++ }
    }
} finally { $stream.Close() }
"zero_blocks=$z / $total (sampled)" | Out-File -Append $log
if ($z -gt 0) { "WARN: $z zero block(s) detected - possible read failure" | Out-File -Append $log }
else { "ZERO_SCAN_OK" | Out-File -Append $log }

"=== finished $(Get-Date) ===" | Out-File -Append $log
