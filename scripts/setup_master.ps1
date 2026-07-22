# Setup script for the Windows Master PC
#
# Run this script once to install all dependencies needed by the Master PC
# coordinator, LLM distributor, and PyCUDA distributor.
#
# Requirements:
#   - Python 3.10+ installed and on PATH
#   - Git installed
#   - Internet access to download llama.cpp releases and Python packages
#
# Usage (Run as Administrator in PowerShell):
#   .\scripts\setup_master.ps1

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "=== Jetson Nano Cluster — Master PC Setup ===" -ForegroundColor Cyan
Write-Host "Repository: $RepoRoot"

# ---------------------------------------------------------------------------
# 1. Check Python
# ---------------------------------------------------------------------------
Write-Host "`n[1/4] Checking Python..." -ForegroundColor Yellow
$PythonCmd = Get-Command python -ErrorAction SilentlyContinue
if (-not $PythonCmd) {
    Write-Error "Python not found on PATH. Install Python 3.10+ and re-run."
    exit 1
}
$PythonVersion = & python --version
Write-Host "  Found: $PythonVersion"

# ---------------------------------------------------------------------------
# 2. Install Python dependencies
# ---------------------------------------------------------------------------
Write-Host "`n[2/4] Installing Python dependencies..." -ForegroundColor Yellow
& python -m pip install --upgrade pip
& python -m pip install -r "$RepoRoot\master\requirements.txt"

# ---------------------------------------------------------------------------
# 3. Download llama.cpp binaries (Windows x64)
# ---------------------------------------------------------------------------
Write-Host "`n[3/4] Downloading llama.cpp binaries..." -ForegroundColor Yellow

$LlamaCppDir = "$RepoRoot\bin\llama-cpp"
New-Item -ItemType Directory -Force -Path $LlamaCppDir | Out-Null

# Fetch the latest release tag from GitHub
$LatestRelease = Invoke-RestMethod `
    -Uri "https://api.github.com/repos/ggerganov/llama.cpp/releases/latest" `
    -Headers @{ "User-Agent" = "JetsonNanoClusterSetup" }

$Tag = $LatestRelease.tag_name
Write-Host "  Latest llama.cpp release: $Tag"

# Find the Windows CUDA asset (adjust pattern if needed)
$Asset = $LatestRelease.assets | Where-Object {
    $_.name -match "llama-.*-bin-win-cuda.*x64\.zip"
} | Select-Object -First 1

if ($Asset) {
    $ZipPath = "$env:TEMP\llama-cpp-win.zip"
    Write-Host "  Downloading $($Asset.name)..."
    Invoke-WebRequest -Uri $Asset.browser_download_url -OutFile $ZipPath
    Expand-Archive -Path $ZipPath -DestinationPath $LlamaCppDir -Force
    Remove-Item $ZipPath
    Write-Host "  Extracted to $LlamaCppDir"
} else {
    Write-Warning "  Could not find a Windows CUDA release asset for $Tag."
    Write-Warning "  Download llama.cpp manually from https://github.com/ggerganov/llama.cpp/releases"
    Write-Warning "  and place llama-cli.exe in $LlamaCppDir"
}

# Add bin dir to the current session PATH
$env:PATH = "$LlamaCppDir;$env:PATH"

# ---------------------------------------------------------------------------
# 4. Verify installation
# ---------------------------------------------------------------------------
Write-Host "`n[4/4] Verifying installation..." -ForegroundColor Yellow

$LlamaCli = Get-Command llama-cli -ErrorAction SilentlyContinue
if ($LlamaCli) {
    Write-Host "  llama-cli found: $($LlamaCli.Source)" -ForegroundColor Green
} else {
    Write-Warning "  llama-cli not on PATH. Add $LlamaCppDir to your system PATH."
}

Write-Host "`n=== Master PC setup complete ===" -ForegroundColor Green
Write-Host "Start the coordinator with:"
Write-Host "  python -m master.coordinator" -ForegroundColor Cyan
