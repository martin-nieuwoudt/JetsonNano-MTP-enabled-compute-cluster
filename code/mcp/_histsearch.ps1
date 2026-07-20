$path = 'c:\Users\marti\AppData\Roaming\Code - Insiders\User\workspaceStorage\a0250be076b26a53ef77b73b8833ec1e\GitHub.copilot-chat\transcripts\8f59f910-efd2-4a33-9326-69f66bd36dc8.jsonl'
$lines = Get-Content -Path $path -Raw -Encoding UTF8
$arr = $lines -split "`n"
foreach ($l in $arr) {
    if ($l -match '192.168.50.160:50052|11-node|all 11 node|llama-cli.exe') {
        $s = $l
        if ($s.Length -gt 400) { $s = $s.Substring(0, 400) }
        Write-Output $s
    }
}
