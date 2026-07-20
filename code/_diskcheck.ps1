$d = Get-PSDrive C
$freeGB = [math]::Round($d.Free/1GB,1)
$usedGB = [math]::Round($d.Used/1GB,1)
Write-Host "C: used=${usedGB}GB free=${freeGB}GB"
Write-Host "--- image files ---"
Get-ChildItem 'C:\Users\marti\Desktop\Cluster\*.img' | ForEach-Object {
    $gb = [math]::Round($_.Length/1GB,1)
    Write-Host ("{0,-40} {1}GB" -f $_.Name, $gb)
}
