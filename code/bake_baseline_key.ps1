<#
.SYNOPSIS
    Bake the PC pubkey into the worker BASELINE image (offline, in place).
.DESCRIPTION
    After running this once, every worker flashed from Jetson_Worker_Baseline.img
    already trusts the PC key -> onboard_worker.sh can SSH in with NO console and
    NO key-paste. Also sets a neutral placeholder hostname so clones don't collide
    on boot (onboard_worker.sh overrides it per-worker anyway).
    Idempotent: re-running just ensures the key is present.
#>
[CmdletBinding()]
param(
    [string]$BaselineImage = "C:\Users\marti\Desktop\Cluster\Jetson_Worker_Baseline.img",
    [string]$PubKeyFile    = "/home/marti/.ssh/id_ed25519_vm"
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $BaselineImage)) { throw "Baseline not found: $BaselineImage" }

# Derive pubkey inside WSL (key lives in /home/marti, not visible to PowerShell)
$pubKey = (wsl -d Ubuntu -u marti bash -c "ssh-keygen -y -P '' -f $PubKeyFile" 2>$null).Trim()
if ([string]::IsNullOrWhiteSpace($pubKey)) { throw "Could not derive PC pubkey from $PubKeyFile" }
Write-Host "PC pubkey : $($pubKey.Substring(0,[Math]::Min(40,$pubKey.Length)))..."

$drive = $BaselineImage.Substring(0,1).ToLower()
$wslPath = "/mnt/$drive" + $BaselineImage.Substring(2).Replace('\','/')

$wsl = @'
set -e
IMG='__IMG__'
lp=$(losetup -fP "$IMG")
losetup -P "$lp" "$IMG" >/dev/null 2>&1 || losetup -fP "$IMG"
L=$(losetup -a | grep "$IMG" | head -1 | cut -d: -f1)
mkdir -p /mnt/imgroot
mount "${L}p1" /mnt/imgroot
PUB='__PUB__'
AD="/mnt/imgroot/home/jetson/.ssh"
mkdir -p "$AD"; chmod 700 "$AD"
if ! grep -q "$(echo "$PUB" | cut -d' ' -f2)" "$AD/authorized_keys" 2>/dev/null; then
    echo "$PUB" >> "$AD/authorized_keys"
fi
chmod 600 "$AD/authorized_keys"
chown -R 1000:1000 "$AD" 2>/dev/null || true
echo "authorized_keys lines: $(wc -l < "$AD/authorized_keys")"
umount /mnt/imgroot; losetup -d "$L"
echo DONE
'@
$wsl = $wsl.Replace('__IMG__',$wslPath).Replace('__PUB__',$pubKey)
$tmp = Join-Path $env:TEMP "bake_baseline.sh"
[System.IO.File]::WriteAllText($tmp, $wsl.Replace("`r`n","`n"))
$tmpWsl = "/mnt/" + $tmp.Substring(0,1).ToLower() + $tmp.Substring(2).Replace('\','/')
wsl -d Ubuntu -u root bash "$tmpWsl" 2>&1 | ForEach-Object { Write-Host "  $_" }
if ($LASTEXITCODE -ne 0) { throw "bake failed (exit $LASTEXITCODE)" }
Write-Host "=== Baseline now trusts the PC key. Flash workers directly from it. ==="
