#!/usr/bin/env pwsh
# Phase 10.5 — Output capture & formatting wrapper for the Jetson RPC cluster.
# Run on the Windows Master PC. Wraps llama-cli.exe (CPU-only RPC client) so that
# generated text is captured to a human-readable file AND (optionally) a structured
# JSON/Markdown report. The Nano nodes are RPC servers and never store output — the
# answer lands on the PC, this script just saves and formats it.
#
# Usage:
#   pwsh code\phase10_capture.ps1 -PromptFile C:\Prompts\q3.txt `
#       -Model C:\Models\Qwen2.5-72B-Instruct-IQ3_XS.gguf `
#       [-GrammarFile C:\Grammars\answer.json.gbnf] [-Tokens 1024] [-OutDir C:\Outputs]
#
# Outputs (in -OutDir, timestamped):
#   <stamp>_<name>.txt      raw human-readable answer (prompt suppressed)
#   <stamp>_<name>.jsonl    full client log (prompt + answer + perf lines)
#   <stamp>_<name>.json     parsed JSON (only if -GrammarFile was a JSON grammar)
#   <stamp>_<name>.md       Markdown summary of the JSON (only if JSON produced)

param(
    [Parameter(Mandatory=$true)]  [string]$PromptFile,
    [Parameter(Mandatory=$true)]  [string]$Model,
    [Parameter(Mandatory=$false)] [string]$GrammarFile = "",
    [Parameter(Mandatory=$false)] [int]   $Tokens = 1024,
    [Parameter(Mandatory=$false)] [string]$OutDir = "C:\Outputs",
    [Parameter(Mandatory=$false)] [string]$RpcList = "192.168.50.150:50052,192.168.50.151:50052,192.168.50.152:50052,192.168.50.153:50052,192.168.50.154:50052,192.168.50.155:50052,192.168.50.156:50052,192.168.50.157:50052,192.168.50.158:50052,192.168.50.159:50052,192.168.50.160:50052",
    [Parameter(Mandatory=$false)] [string]$TensorSplit = "0.85,1,1,1,1,1,1,1,1,1,1",
    [Parameter(Mandatory=$false)] [int]   $CtxSize = 8192
)

$ErrorActionPreference = "Stop"
$cli = "C:\llama.cpp\build\bin\llama-cli.exe"
if (-not (Test-Path $cli)) { Write-Error "llama-cli.exe not found at $cli"; exit 1 }
if (-not (Test-Path $PromptFile)) { Write-Error "Prompt file not found: $PromptFile"; exit 1 }

New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$stamp = Get-Date -Format "yyyy-MM-dd_HHmmss"
$name  = [System.IO.Path]::GetFileNameWithoutExtension($PromptFile)
$base  = Join-Path $OutDir ("${stamp}_${name}")
$txt   = "$base.txt"
$jsonl = "$base.jsonl"

# Build the argument list. --no-display-prompt keeps the .txt to the answer only.
$cliArgs = @(
    "-m", $Model,
    "--flash-attn",
    "--no-display-prompt",
    "--log-file", $jsonl,
    "--rpc", $RpcList,
    "--tensor-split", $TensorSplit,
    "--ctx-size", $CtxSize,
    "-f", $PromptFile,
    "-n", $Tokens
)
if ($GrammarFile -and (Test-Path $GrammarFile)) {
    $cliArgs += @("--grammar-file", $GrammarFile)
}

Write-Host ">> Running cluster inference (output -> $txt)"
& $cli @cliArgs > $txt 2>&1
$rc = $LASTEXITCODE
Write-Host ">> llama-cli exited with code $rc"

if ($rc -ne 0) {
    Write-Warning "Client returned non-zero; inspect $txt and $jsonl"
}

# If a JSON grammar was used, try to extract + pretty-print + summarise.
if ($GrammarFile -and (Test-Path $GrammarFile)) {
    $raw = Get-Content -Raw $txt
    # Best-effort: grab the first {...} block (grammar should emit a single JSON object)
    if ($raw -match '(?s)\{.*\}') {
        $jsonText = $Matches[0]
        try {
            $obj = $jsonText | ConvertFrom-Json
            $jsonOut = "$base.json"
            $obj | ConvertTo-Json -Depth 10 | Set-Content -Encoding UTF8 $jsonOut
            $mdOut = "$base.md"
            "# Cluster Inference Result — $name`n`n_Generated $(Get-Date -Format u)_`n`n" |
                Set-Content -Encoding UTF8 $mdOut
            $obj.PSObject.Properties | ForEach-Object {
                "`## $($_.Name)`n`n$($_.Value)`n" | Add-Content -Encoding UTF8 $mdOut
            }
            Write-Host ">> Wrote structured outputs: $jsonOut, $mdOut"
        } catch {
            Write-Warning "Grammar was JSON but result did not parse; leaving raw .txt only."
        }
    }
}

Write-Host ">> Done. Human-readable answer: $txt"
