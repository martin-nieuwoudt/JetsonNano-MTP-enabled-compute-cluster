# build_pc_release.ps1
# Rebuilds PC llama.cpp in Release (was Debug -> VC++ runtime crash).
# MUST run inside VS 2022 Developer Prompt so nvcc finds cl.exe (MSVC).
# Logs to C:\Models\pc_build.log
$ErrorActionPreference = "Continue"
$log = "C:\Models\pc_build.log"
$src = "C:\llama.cpp"
$build = "C:\llama.cpp\build"
$vsdev = "C:\Program Files\Microsoft Visual Studio\18\Community\Common7\Tools\VsDevCmd.bat"
function Log($m){ $t = Get-Date -Format "yyyy-MM-dd HH:mm:ss"; "$t  $m" | Tee-Object -FilePath $log -Append }

Log "=== PC llama.cpp Release rebuild start (VS2022 env) ==="

# Launch everything inside the VS developer environment
$cmd = @"
call "$vsdev" >nul 2>&1
cd /d "$build"
if exist CMakeCache.txt del /f CMakeCache.txt
if exist CMakeFiles rmdir /s /q CMakeFiles
"C:\Strawberry\c\bin\cmake.EXE" -G Ninja -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=ON -DBUILD_SHARED_LIBS=ON -DCMAKE_C_COMPILER=cl -DCMAKE_CXX_COMPILER=cl "$src" >> "$log" 2>&1
if errorlevel 1 (echo CMAKE CONFIG FAILED >> "$log" & exit /b 1)
"C:\Strawberry\c\bin\cmake.EXE" --build . --config Release -j 24 >> "$log" 2>&1
if errorlevel 1 (echo BUILD FAILED >> "$log" & exit /b 1)
echo PC Release build complete >> "$log"
"@
$cmd | Out-File -FilePath "C:\Models\build_step.bat" -Encoding ascii

Log "running build_step.bat in VS env..."
cmd.exe /c "C:\Models\build_step.bat" | Out-Null
Log "=== build_step.bat finished (see log for result) ==="
