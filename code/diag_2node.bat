@echo off
"C:\llama.cpp-mtp\build\bin\llama-cli.exe" -m "C:\Models\Phi-3-mini-4k-instruct-Q6_K.gguf" -p "hi" -n 8 --rpc "192.168.50.150:50052,192.168.50.151:50052" --no-display-prompt -ngl 0 > "C:\Users\marti\Desktop\Cluster\code\diag_2node.out" 2> "C:\Users\marti\Desktop\Cluster\code\diag_2node.err"
echo EXIT=%ERRORLEVEL% >> "C:\Users\marti\Desktop\Cluster\code\diag_2node.err"
