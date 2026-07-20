$ErrorActionPreference = "Stop"
$cli = "C:\Python314\python.exe"
$script = "C:\Users\marti\Desktop\Cluster\code\cluster_infer.py"
$model = "C:\Models\Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf"
$sysfile = "C:\Users\marti\Desktop\Cluster\System Prompt.md"
$prompt = "You are the Strategist for the Anti-Dark-Forest research programme. State the core thesis of Biology as Bounded Information: that a civilisation which destroys or hides from others (the Dark Forest strategy) is thermodynamically and information-theoretically suboptimal compared with one that assimilates, simulates, and seeds. Then outline the six propositions P1 through P6 and, for each, name the simulation method that would test it."
$out = "C:\Users\marti\Desktop\Cluster\code\qwythos_p1_v4.json"
$err = "C:\Users\marti\Desktop\Cluster\code\qwythos_p1_v4.err"

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $cli
function Quote-Arg($a) {
    if ($a -match '\s') { return '"' + $a + '"' } else { return $a }
}
$psi.Arguments = (@(
    $script,
    "--build", "mtp",
    "--nodes", "all",
    "--model", $model,
    "--prompt", $prompt,
    "--tokens", "512",
    "--ctx-size", "4096",
    "--tensor-split", "1,1,1,1,1,1,1,1,1,1,1",
    "--system-file", $sysfile,
    "--no-qos",
    "--json"
) | ForEach-Object { Quote-Arg $_ }) -join " "
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.UseShellExecute = $false

$p = New-Object System.Diagnostics.Process
$p.StartInfo = $psi
$p.Start() | Out-Null
if (-not $p.WaitForExit(600000)) {
    "TIMEOUT - killing"
    $p.Kill()
}
[System.IO.File]::WriteAllText($out, $p.StandardOutput.ReadToEnd())
[System.IO.File]::WriteAllText($err, $p.StandardError.ReadToEnd())
"=== STATE ==="
"EXIT=$($p.ExitCode)"
"OUT bytes: $((Get-Item $out -ErrorAction SilentlyContinue).Length)"
"ERR tail:"
Get-Content $err -Tail 15
