$ErrorActionPreference = 'Stop'
$up = Test-Connection -ComputerName 192.168.50.150 -Count 2 -Quiet
Write-Output ("node0 ping: " + $up)
try {
    $items = Get-ChildItem '\\192.168.50.150\ssd' -ErrorAction Stop
    Write-Output ('SSD root items: ' + $items.Count)
    foreach ($i in $items) { Write-Output ('  ' + $i.Name + '  ' + $i.Length) }
    $models = Join-Path '\\192.168.50.150\ssd' 'models'
    if (Test-Path $models) {
        $m = Get-ChildItem $models
        Write-Output ('models/ items: ' + $m.Count)
        foreach ($i in $m) { Write-Output ('  ' + $i.Name + '  ' + $i.Length) }
    } else {
        Write-Output 'models/ does NOT exist yet'
    }
} catch {
    Write-Output ('SMB err: ' + $_.Exception.Message)
}
