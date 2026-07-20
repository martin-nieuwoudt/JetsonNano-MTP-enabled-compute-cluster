Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object { $_.CommandLine -like '*backup_node1.ps1*' } | ForEach-Object {
    "killing backup pid $($_.ProcessId)"
    Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
Get-Process dd -ErrorAction SilentlyContinue | ForEach-Object {
    "killing dd pid $($_.Id)"
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}
"done"
