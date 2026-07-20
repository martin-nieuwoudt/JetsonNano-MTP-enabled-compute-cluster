@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\Common7\Tools\VsDevCmd.bat" -vcvars_ver=14.44 -arch=x64 >nul 2>&1
for /f "usebackq delims=" %%P in (`powershell -NoProfile -Command "$p=$env:PATH -split ';' | Where-Object { $_ -and ($_ -notmatch 'git') -and ($_ -notmatch 'strawberry') -and ($_ -notmatch 'msys') }; $p -join ';'"`) do set "PATH=%%P"
echo SH on PATH:
where sh.exe 2>nul || echo NONE
echo --- nvcc 13.3 trivial test (sm_120) ---
echo extern "C" __global__ void k(){} > t13.cu
"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v13.3\bin\nvcc.exe" -ccbin "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64" --allow-unsupported-compiler -arch=sm_120 t13.cu -o t13.obj 2>&1
echo NVCC13_EXIT=%errorlevel%
