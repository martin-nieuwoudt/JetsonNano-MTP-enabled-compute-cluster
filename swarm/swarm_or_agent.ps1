# swarm_or_agent.ps1
# Manually call ONE OpenRouter free model as an agent on ONE CUDA shard.
# Reads the API key from $env:OPENROUTER_API_KEY (set it yourself in the terminal).
#
# Usage:
#   $env:OPENROUTER_API_KEY = "sk-or-..."      # you type this, not the assistant
#   .\swarm_or_agent.ps1 -Model "deepseek/deepseek-chat-v3-0324:free" -Shard 1
#   .\swarm_or_agent.ps1 -Model "meta-llama/llama-3.3-70b-instruct:free" -Shard 3
#
# Shards (see swarm_deploy.sh):
#   1 = common.cuh (critical path)        2 = convert.cuh + BF16 shim
#   3 = gated_delta_net.cu              4 = other MTP-only files
#   5 = fattn/mmq/mmvq/rope/norm/etc
#
# Each call: pulls the shard file(s) from node0, sends to OpenRouter with the
# C++17->C++14 port brief, writes the patched file back, logs the diff.

param(
    [Parameter(Mandatory=$true)]  [string]$Model,
    [Parameter(Mandatory=$true)]  [int]   $Shard
)

$NODE0 = "jetson@192.168.50.150"
$SRC  = "/home/jetson/llama.cpp-mtp/ggml/src/ggml-cuda"
$WORK = Join-Path $PSScriptRoot "_work"

$SHARDS = @{
  1 = @("common.cuh")
  2 = @("convert.cuh","vendors/cuda_bf16.h","vendors/cuda.h")
  3 = @("gated_delta_net.cu")
  4 = @("col2im-1d.cu","col2im-1d.cuh","fwht.cu","fwht.cuh","snake.cu","snake.cuh","mmq-instance-nvfp4.cu")
  5 = @("fattn.cu","fattn-mma-f16.cuh","fattn-tile.cuh","fattn-vec.cuh","fattn-common.cuh",
         "mmq.cuh","mmq.cu","mmvq.cu","rope.cu","norm.cu","concat.cu","topk-moe.cu","mma.cuh",
         "mmf.cuh","mmvf.cu","mmid.cu","tri.cu","binbcast.cu")
}

if (-not $env:OPENROUTER_API_KEY) { Write-Error "Set `$env:OPENROUTER_API_KEY first (in your terminal, not chat)."; exit 1 }
if (-not $SHARDS.ContainsKey($Shard)) { Write-Error "Shard $Shard not defined (1-5)."; exit 1 }

$BRIEF = @"
You are porting CUDA C++ from C++17 to C++14 to compile under NVCC 10.2 on a Jetson Nano (CUDA 10.2, max C++14).
TARGET standard: C++14 (ISO/IEC 14882:2014, N4140). FORBIDDEN in C++14 device code:
 - `if constexpr(...)` at statement scope -> rewrite as plain `if (...)` ONLY when every discarded branch holds only a dependent `static_assert` (then it is semantically identical). Otherwise use tag dispatch / template specialization.
 - `std::is_same_v<T,Ts>` -> `std::is_same<T,Ts>::value`
 - `std::string_view`, `std::filesystem`, `std::optional` (pre-C++17), structured bindings, fold expressions, `std::variant`, `std::any`, `std::byte`, inline variables.
CRITICAL: never replace a real operation body with a stub/(void)0. The known trap is binbcast.cu fold expressions being zeroed -> compiles but produces garbage. Preserve all computation.
Return ONLY the full rewritten file content, no commentary, no markdown fences.
"@

New-Item -ItemType Directory -Force -Path $WORK | Out-Null

foreach ($rel in $SHARDS[$Shard]) {
    $name = Split-Path $rel -Leaf
    # pull from node0
    $wslWork = "/mnt/c/" + ($WORK -replace '^C:\\','' -replace '\\','/')
    & wsl -d Ubuntu -e bash -c "scp -o BatchMode=yes '$NODE0`:$SRC/$rel' '$wslWork/$name'"
    if (-not (Test-Path "$WORK\$name")) { Write-Warning "Pull failed: $rel"; continue }
    $code = Get-Content "$WORK\$name" -Raw -Encoding UTF8

    $body = @{
        model = $Model
        messages = @(
            @{ role = "system"; content = $BRIEF },
            @{ role = "user";   content = "Rewrite this file to C++14:`n`n$code" }
        )
        temperature = 0
    } | ConvertTo-Json -Depth 5

    try {
        $resp = Invoke-RestMethod -Uri "https://openrouter.ai/api/v1/chat/completions" `
            -Method Post -ContentType "application/json" `
            -Headers @{ Authorization = "Bearer $env:OPENROUTER_API_KEY" } `
            -Body $body -TimeoutSec 300
        $patched = $resp.choices[0].message.content
        # strip accidental fences
        $patched = $patched -replace '^```[a-zA-Z]*\s*','' -replace '```\s*$',''
        Set-Content "$WORK\$name" $patched -Encoding UTF8
        # push back to node0
        & wsl -d Ubuntu -e bash -c "scp -o BatchMode=yes '$wslWork/$name' '$NODE0`:$SRC/$rel'"
        "Shard $Shard / $rel -> patched by $Model, pushed to node0."
    } catch {
        "ERROR on $rel : $_"
    }
}
