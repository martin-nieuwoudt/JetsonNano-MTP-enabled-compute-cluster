# build_pc_release_mtp.ps1
# Builds the MTP-capable llama.cpp (tag b9886) in Release for the PC client.
# Parallel secondary build to the pinned stable one (C:\llama.cpp @ b56f079e2).
# MUST run inside VS 2022 Developer Prompt so nvcc finds cl.exe (MSVC).
# Logs to C:\Models\pc_build_mtp.log
$ErrorActionPreference = "Continue"
$log = "C:\Models\pc_build_mtp.log"
$cmakelog = "C:\Models\pc_build_mtp_cmake.log"
$src = "C:\llama.cpp-mtp"
$build = "C:\llama.cpp-mtp\build"
$vsdev = "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvarsall.bat"
function Log($m){ $t = Get-Date -Format "yyyy-MM-dd HH:mm:ss"; "$t  $m" | Tee-Object -FilePath $log -Append }

Log "=== PC llama.cpp-MTP (b9886) Release rebuild start (VS2022 env) ==="

$cmd = @"
call "$vsdev" x64 -vcvars_ver=14.44.35207 >nul 2>&1
cd /d "$build"
if exist CMakeCache.txt del /f CMakeCache.txt
if exist CMakeFiles rmdir /s /q CMakeFiles
"C:\Strawberry\c\bin\cmake.EXE" -G Ninja -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=OFF -DGGML_RPC=ON -DBUILD_SHARED_LIBS=ON -DCMAKE_C_COMPILER=cl -DCMAKE_CXX_COMPILER=cl "$src" >> "$cmakelog" 2>&1
if errorlevel 1 (echo CMAKE CONFIG FAILED >> "$log" & exit /b 1)
"C:\Strawberry\c\bin\cmake.EXE" --build . --config Release -j 24 >> "$cmakelog" 2>&1
if errorlevel 1 (echo BUILD FAILED >> "$log" & exit /b 1)
echo PC MTP Release build complete >> "$log"
"@
$cmd | Out-File -FilePath "C:\Models\build_step_mtp.bat" -Encoding ascii

Log "running build_step_mtp.bat in VS env..."
cmd.exe /c "C:\Models\build_step_mtp.bat" | Out-Null
Log "=== build_step_mtp.bat finished (see log for result) ==="
