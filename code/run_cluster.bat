# run_cluster.bat — Full Cluster Orchestration Batch Script
# From: raw refinements.md — Final section
# Sits on Windows 11 host alongside cluster_deploy.py and llama.cpp build.
# Completely automates: init Nanos, boot RPC engines, map 11 static IPs,
# format --rpc parameter string, execute large-context batch task.

@echo off
SETLOCAL EnableDelayedExpansion
title Llama.cpp 11-Node Jetson Nano Cluster Orchestrator

:: ==========================================
:: HOST PATH CONFIGURATION
:: ==========================================
SET "LLAMA_DIR=C:\path\to\your\llama.cpp"
SET "MODEL_PATH=C:\Models\Llama-3-32B-Q4_K_M.gguf"
SET "PYTHON_SCRIPT=C:\path\to\your\cluster_deploy.py"

:: Large-Context Task Parameters (Optimized for coding/writing batches)
SET "CTX_SIZE=16384"
SET "BATCH_SIZE=512"
SET "TOKENS_TO_GEN=2048"
SET "INPUT_PROMPT=Write a complete, highly optimized, memory-efficient bare-metal C++ matrix multiplication kernel utilizing ARM NEON assembly intrinsics for a Cortex-A57 architecture. Include strict boundary condition checks."

:: ==========================================
:: STEP 1: CONSTRUCT THE RPC ENDPOINT STRING
:: ==========================================
echo [HOST] Constructing 11-Node Star Topology RPC String...
SET "RPC_STRING="
FOR /L %%I IN (0,1,10) DO (
    set /a "IP_SUFFIX=150 + %%I"
    if %%I==0 (
        SET "RPC_STRING=192.168.50.!IP_SUFFIX!:50052"
    ) else (
        SET "RPC_STRING=!RPC_STRING!,192.168.50.!IP_SUFFIX!:50052"
    )
)
echo [HOST] Structured Endpoint Pool Map:
echo !RPC_STRING!
echo.

:: ==========================================
:: STEP 2: INITIALISE AND START COLD HARDWARE
:: ==========================================
echo [CLUSTER] Pinging Python manager to apply hardware performance profiles...
python "%PYTHON_SCRIPT%" init
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Cluster initialization failed. Verify network switch power.
    pause
    exit /b %ERRORLEVEL%
)
echo.

echo [CLUSTER] Launching bare-metal rpc-server daemons...
python "%PYTHON_SCRIPT%" start
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to start remote RPC engines.
    pause
    exit /b %ERRORLEVEL%
)
:: Give the remote daemons 3 seconds to spin up sockets and bind memory
timeout /t 3 /nobreak >nul
echo.

:: ==========================================
:: STEP 3: RUN THE BATCH INFERENCE PROCESS
:: ==========================================
echo [EXECUTION] Initiating high-context matrix math processing loop...
echo [EXECUTION] Processing Model: %MODEL_PATH%
echo.

cd /d "%LLAMA_DIR%"
build\bin\Release\llama-cli.exe ^
  -m "%MODEL_PATH%" ^
  -p "%INPUT_PROMPT%" ^
  -n %TOKENS_TO_GEN% ^
  -c %CTX_SIZE% ^
  -b %BATCH_SIZE% ^
  --flash-attn ^
  --cache-type-k q8_0 ^
  --cache-type-v q8_0 ^
  --rpc !RPC_STRING!

set "EXEC_STATUS=%ERRORLEVEL%"
echo.
echo ==========================================
echo [EXECUTION] Inference sequence terminated with exit code: %EXEC_STATUS%
echo ==========================================
echo.

:: ==========================================
:: STEP 4: CLEAN RECLAIM OR SHUTDOWN CYCLE
:: ==========================================
CHOICE /C YN /M "[WORKFLOW] Batch complete. Do you want to completely SHUT DOWN the 11 hardware nodes now"

if %ERRORLEVEL% EQU 1 (
    echo [CLUSTER] Sending clean bare-metal hardware power-off signals...
    python "%PYTHON_SCRIPT%" shutdown
) else (
    echo [CLUSTER] Killing background server tasks to flush memory leakage pools...
    python "%PYTHON_SCRIPT%" stop
)

echo [HOST] Script process finished. Exiting.
pause
ENDLOCAL