<#
.SYNOPSIS
    Bake per-worker identity (hostname + static IP) into a copy of the
    Jetson worker baseline image, OFFLINE (no boot needed).

.DESCRIPTION
    Every cloned worker card inherits node1's identity (hostname nano01,
    IP 192.168.50.151). This script makes a per-worker COPY of the baseline
    image and patches, inside the rootfs partition:
      - /etc/hostname              -> nanoNN
      - /etc/hosts                 -> 127.0.1.1 nanoNN  (also fixes the stale
                                      "127.0.1.1 nano" mismatch on the baseline)
      - /etc/NetworkManager/system-connections/Wired connection 1.nmconnection
                                  -> ipv4 address1 = 192.168.50.NN/24,192.168.50.1
    The patched copy is what you flash to the physical card. The original
    Jetson_Worker_Baseline.img is NEVER modified.

    Identity mapping is derived from code/mcp/cluster_config.py (single source
    of truth): .150=nano00 (node0, do NOT use this script for it),
    .151=nano01 ... .160=nano10.

.PARAMETER WorkerNumber
    Worker index 1..10 (maps to nano01..nano10 / .151..160).

.PARAMETER BaselineImage
    Path to the pristine shrunk baseline image. Default:
    C:\Users\marti\Desktop\Cluster\Jetson_Worker_Baseline.img

.PARAMETER OutDir
    Directory for the per-worker image copy. Default: same dir as baseline.

.PARAMETER Gateway
    LAN gateway / DNS. Default 192.168.50.1.

.EXAMPLE
    .\prepare_worker_image.ps1 -WorkerNumber 2
    -> produces Jetson_Worker_nano02.img (hostname nano02, IP .152)
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateRange(1,10)]
    [int]$WorkerNumber,

    [string]$BaselineImage = "C:\Users\marti\Desktop\Cluster\Jetson_Worker_Baseline.img",

    [string]$OutDir = "",

    [string]$Gateway = "192.168.50.1",

    # PC pubkey the cluster trusts. Default: the correct WSL key
    # (id_ed25519_vm, fp clQngg9C...). A .pub sibling is used if present,
    # otherwise the pubkey is derived from the private key. Override only if you must.
    [string]$PubKeyFile = "/home/marti/.ssh/id_ed25519_vm"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $BaselineImage)) {
    throw "Baseline image not found: $BaselineImage"
}

# --- derive identity from cluster_config.py (single source of truth) -------
$ipLast = 150 + $WorkerNumber          # .151..160
$ip     = "192.168.50.$ipLast"
$name   = "nano{0:00}" -f $WorkerNumber

# --- derive PC pubkey (the one the cluster trusts) -------------------------
# The key lives in WSL (/home/marti/...), not visible to Windows PowerShell,
# so derive the pubkey INSIDE wsl via ssh-keygen -y on the private key.
$pubKey = (wsl -d Ubuntu -u marti bash -c "ssh-keygen -y -P '' -f $PubKeyFile" 2>$null).Trim()
if ([string]::IsNullOrWhiteSpace($pubKey)) {
    throw "Could not derive PC pubkey from $PubKeyFile (is the WSL key present?)"
}
Write-Host "PC pubkey : $($pubKey.Substring(0, [Math]::Min(40,$pubKey.Length)))..."

if ($OutDir -eq "") { $OutDir = Split-Path $BaselineImage -Parent }
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }

$outImg = Join-Path $OutDir ("Jetson_Worker_{0}.img" -f $name)

Write-Host "=== prepare_worker_image ==="
Write-Host "Worker # : $WorkerNumber"
Write-Host "Hostname : $name"
Write-Host "IP       : $ip/24  (gw/dns $Gateway)"
Write-Host "Source   : $BaselineImage"
Write-Host "Output   : $outImg"

# --- 1. copy baseline -> per-worker image (do NOT touch the original) ------
if (Test-Path $outImg) {
    Write-Host "Removing existing $outImg ..."
    Remove-Item $outImg -Force
}
Write-Host "Copying baseline -> per-worker image (this may take a few min) ..."
Copy-Item -Path $BaselineImage -Destination $outImg -Force
Write-Host "Copy done."

# --- 2. offline patch via WSL loop mount -----------------------------------
# Convert Windows path C:\foo\bar.img -> /mnt/c/foo/bar.img for WSL
$drive = $outImg.Substring(0,1).ToLower()
$wslPath = "/mnt/$drive" + $outImg.Substring(2).Replace('\','/')

$wslScript = @'
set -e
IMG='__IMG__'
echo "MOUNT_IMG=$IMG"
lp=$(losetup -fP "$IMG" && losetup -a | grep "$IMG" | cut -d: -f1)
echo "LOOP=$lp"
mkdir -p /mnt/imgroot
mount "${lp}p1" /mnt/imgroot

echo '=== /etc/hostname ==='
printf '%s\n' '__NAME__' > /mnt/imgroot/etc/hostname
cat /mnt/imgroot/etc/hostname

echo '=== /etc/hosts (fix 127.0.1.1 mismatch) ==='
if grep -q '^127.0.1.1' /mnt/imgroot/etc/hosts; then
    sed -i "s/^127.0.1.1.*/127.0.1.1       __NAME__/" /mnt/imgroot/etc/hosts
else
    printf '127.0.1.1       %s\n' '__NAME__' >> /mnt/imgroot/etc/hosts
fi
grep '127.0.1.1' /mnt/imgroot/etc/hosts

echo '=== NM keyfile ipv4.address1 ==='
NMF="/mnt/imgroot/etc/NetworkManager/system-connections/Wired connection 1.nmconnection"
sed -i "s#^address1=.*#address1=__IP__/24,__GW__#" "$NMF"
grep '^address1=' "$NMF"

echo '=== inject PC pubkey into jetson authorized_keys (offline) ==='
# Bake the PC key the cluster trusts (id_ed25519_vm, fp clQngg9C...) so every
# flashed worker is reachable from the PC with NO console key-paste and NO
# password auth. Idempotent: skip if already present.
PUB='__PUB__'
AD="/mnt/imgroot/home/jetson/.ssh"
mkdir -p "$AD"
chmod 700 "$AD"
if ! grep -q "$(echo "$PUB" | cut -d' ' -f2)" "$AD/authorized_keys" 2>/dev/null; then
    echo "$PUB" >> "$AD/authorized_keys"
fi
chmod 600 "$AD/authorized_keys"
chown -R 1000:1000 "$AD" 2>/dev/null || true   # jetson uid:gid = 1000:1000
echo "authorized_keys lines: $(wc -l < "$AD/authorized_keys")"

umount /mnt/imgroot
losetup -d "$lp"
echo 'LOOP_RELEASED'
'@
# Inject dynamic values (single-quoted here-string keeps $ and bash syntax literal)
$wslScript = $wslScript.Replace('__IMG__', $wslPath).Replace('__NAME__', $name).Replace('__IP__', $ip).Replace('__GW__', $Gateway).Replace('__PUB__', $pubKey)

Write-Host "Patching image offline (WSL loop mount) ..."
$tmpSh = Join-Path $env:TEMP "prep_worker.sh"
# Write with UNIX LF line endings only — bash breaks on Windows CRLF (\r)
[System.IO.File]::WriteAllText($tmpSh, $wslScript.Replace("`r`n","`n"))
# Run the script by its WSL path (no pipe/redirect — avoids PowerShell/WSL plumbing issues)
$tmpWsl = "/mnt/" + $tmpSh.Substring(0,1).ToLower() + $tmpSh.Substring(2).Replace('\','/')
wsl -d Ubuntu -u root bash "$tmpWsl" 2>&1 | ForEach-Object { Write-Host "  $_" }

if ($LASTEXITCODE -ne 0) {
    throw "WSL patch step failed (exit $LASTEXITCODE). Image $outImg may be half-patched — delete and retry."
}

Write-Host ""
Write-Host "=== DONE: $outImg is ready to flash ==="
Write-Host "  hostname = $name"
Write-Host "  IP       = $ip/24"
Write-Host "Flash this image to the physical SD card for worker #$WorkerNumber."
