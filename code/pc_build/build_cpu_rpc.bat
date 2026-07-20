@echo off
REM ============================================================================
REM PC ORCHESTRATOR BUILD — CPU-only + RPC client (NO CUDA)
REM ----------------------------------------------------------------------------
REM Purpose: Build llama-cli on the Windows 11 PC as a pure RPC *client*.
REM The PC does NOT run any GPU math. It slices the model graph and ships
REM tensor chunks to the Jetson Nano RPC servers, which do the Maxwell GPU
REM compute. This keeps the RTX 5060 completely free for other work while a
REM batch job is submitted to the cluster.
REM
REM CRITICAL: This MUST be built from the SAME llama.cpp commit as the Nano
REM rpc-server (b56f079e2). The RPC wire protocol changes between commits, so
REM client and server must match exactly or the connection will fail.
REM
REM Commit: b56f079e2  (last commit before CUDA 11.0 BF16 support was added;
REM          the newest commit that still compiles under JetPack 4.6.1 /
REM          CUDA 10.2 on the Jetson Nano)
REM ============================================================================

call "C:\Program Files\Microsoft Visual Studio\18\Community\Common7\Tools\VsDevCmd.bat" -vcvars_ver=14.44 -arch=x64 >nul 2>&1

cd /d C:\llama.cpp
git checkout b56f079e2

cd /d C:\llama.cpp\build
if exist CMakeCache.txt del /f CMakeCache.txt
if exist CMakeFiles rmdir /s /q CMakeFiles

set "LOG=C:\Users\marti\Desktop\Cluster\code\pc_build\cfg_cpu_rpc.log"

"C:\Strawberry\c\bin\cmake.EXE" -G Ninja -DCMAKE_MAKE_PROGRAM=C:\Strawberry\c\bin\ninja.exe ^
  -DCMAKE_BUILD_TYPE=Release ^
  -DGGML_CUDA=OFF ^
  -DGGML_RPC=ON ^
  -DBUILD_SHARED_LIBS=ON ^
  -DCMAKE_C_COMPILER=cl ^
  -DCMAKE_CXX_COMPILER=cl ^
  C:\llama.cpp > "%LOG%" 2>&1
if errorlevel 1 (
  echo CMAKE CONFIG FAILED >> "%LOG%"
  exit /b 1
)
echo CONFIG_OK >> "%LOG%"

"C:\Strawberry\c\bin\cmake.EXE" --build . --config Release -j 24 >> "%LOG%" 2>&1
if errorlevel 1 (
  echo BUILD FAILED >> "%LOG%"
  exit /b 1
)
echo PC CPU+RPC build complete >> "%LOG%"
