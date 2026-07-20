@echo off
REM Sanitize PATH: remove sh.exe/make.exe sources that break nvcc (cudafe++ ACCESS_VIOLATION)
REM Pin to MSVC 14.44 toolset — CUDA 12.6 rejects newer 14.5x compilers
call "C:\Program Files\Microsoft Visual Studio\18\Community\Common7\Tools\VsDevCmd.bat" -vcvars_ver=14.44 -arch=x64 >nul 2>&1

REM Case-insensitive PATH strip via PowerShell (robust). Removes Git/Strawberry/msys
REM dirs that supply sh.exe/make.exe which crash cudafe++.
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "$p=$env:PATH -split ';' | Where-Object { $_ -and ($_ -notmatch 'git') -and ($_ -notmatch 'strawberry') -and ($_ -notmatch 'msys') }; $p -join ';'"`) do set "PATH=%%P"

cd /d C:\llama.cpp\build
if exist CMakeCache.txt del /f CMakeCache.txt
if exist CMakeFiles rmdir /s /q CMakeFiles

set "CUDA_ROOT=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.3"
set "CUDAFLAGS=--allow-unsupported-compiler"
set "LOG=C:\Users\marti\Desktop\Cluster\code\pc_build\cfg_final.log"

echo PATH_CHECK_SH: > "%LOG%"
where sh.exe >> "%LOG%" 2>&1 || echo "no sh.exe in PATH" >> "%LOG%"

"C:\Strawberry\c\bin\cmake.EXE" -G Ninja -DCMAKE_MAKE_PROGRAM=C:\Strawberry\c\bin\ninja.exe ^
  -DCMAKE_BUILD_TYPE=Release ^
  -DGGML_CUDA=ON ^
  -DGGML_RPC=ON ^
  -DBUILD_SHARED_LIBS=ON ^
  -DCMAKE_C_COMPILER=cl ^
  -DCMAKE_CXX_COMPILER=cl ^
  -DCUDAToolkit_ROOT="%CUDA_ROOT%" ^
  -DCMAKE_CUDA_COMPILER="%CUDA_ROOT%\bin\nvcc.exe" ^
  -DCMAKE_CUDA_FLAGS="--allow-unsupported-compiler" ^
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
echo PC Release build complete >> "%LOG%"
