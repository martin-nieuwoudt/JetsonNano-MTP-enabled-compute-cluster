$src = Get-Content 'C:\Users\marti\Desktop\Cluster\code\backup_node1_auto.ps1' -Raw
$tokens = $null; $errs = $null
[System.Management.Automation.Language.Parser]::ParseInput($src, [ref]$tokens, [ref]$errs)
if ($errs) { $errs | ForEach-Object { $_.Message } } else { 'SYNTAX_OK' }
