call "C:\Program Files\Microsoft Visual Studio\18\Community\Common7\Tools\VsDevCmd.bat" >nul 2>&1
cd /d "C:\llama.cpp\build"
if exist CMakeCache.txt del /f CMakeCache.txt
if exist CMakeFiles rmdir /s /q CMakeFiles
"C:\Strawberry\c\bin\cmake.EXE" -G Ninja -DCMAKE_BUILD_TYPE=Release -DGGML_CUDA=ON -DBUILD_SHARED_LIBS=ON -DCMAKE_C_COMPILER=cl -DCMAKE_CXX_COMPILER=cl "C:\llama.cpp" >> "C:\Models\pc_build.log" 2>&1
if errorlevel 1 (echo CMAKE CONFIG FAILED >> "C:\Models\pc_build.log" & exit /b 1)
"C:\Strawberry\c\bin\cmake.EXE" --build . --config Release -j 24 >> "C:\Models\pc_build.log" 2>&1
if errorlevel 1 (echo BUILD FAILED >> "C:\Models\pc_build.log" & exit /b 1)
echo PC Release build complete >> "C:\Models\pc_build.log"
