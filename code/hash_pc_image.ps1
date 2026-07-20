# Compute SHA256 of the first 63864569856 bytes of the image (raw card size,
# excludes the 2 MiB dd trailing partial-block padding) so it is directly
# comparable to the node1 live-card hash (sudo sha256sum /dev/mmcblk0).
$img = 'C:\Users\marti\Desktop\Cluster\Jetson_Worker_Node1_FullBackup_2026-07-12.img'
$limit = 63864569856
$out = 'C:\Users\marti\Desktop\Cluster\pc_image.sha256'

$sha = [System.Security.Cryptography.SHA256]::Create()
$buf = New-Object byte[] 8MB
$total = 0
$stream = [System.IO.File]::OpenRead($img)
try {
    while ($total -lt $limit) {
        $toRead = [Math]::Min([long]$buf.Length, [long]($limit - $total))
        $n = $stream.Read($buf, 0, $toRead)
        if ($n -le 0) { break }
        $sha.TransformBlock($buf, 0, $n, $null, 0) | Out-Null
        $total += $n
    }
} finally {
    $stream.Close()
}
$sha.TransformFinalBlock($buf, 0, 0) | Out-Null
$hex = [BitConverter]::ToString($sha.Hash).Replace('-', '').ToLower()
"$hex  $img (first $total bytes)" | Set-Content -Path $out
Write-Host "PC image SHA256: $hex"
Write-Host "Bytes hashed: $total"
Write-Host "Written to: $out"
