@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\Common7\Tools\VsDevCmd.bat" -vcvars_ver=14.44 >nul 2>&1
set "PATH=%PATH:C:\Program Files\Git\usr\bin;=%"
set "PATH=%PATH:C:\Program Files\Git\bin;=%"
set "PATH=%PATH:C:\Strawberry\c\bin;=%"
set "PATH=%PATH:C:\msys64\ucrt64\bin;=%"
echo SH on PATH:
where sh.exe 2>nul || echo NONE
echo --- nvcc trivial test ---
echo extern "C" __global__ void k(){} > t.cu
"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.6\bin\nvcc.exe" -ccbin "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64" t.cu -o t.obj 2>&1
echo NVCC_EXIT=%errorlevel%
