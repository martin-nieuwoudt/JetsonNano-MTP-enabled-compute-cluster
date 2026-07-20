@echo off
set RPC=192.168.50.150:50053
"C:\llama.cpp-mtp\build\bin\llama-cli.exe" -m "C:\Models\Qwythos-9B-Claude-Mythos-5-1M-MTP-Q8_0.gguf" -p "State the core thesis of Biology as Bounded Information in one sentence." -n 64 -c 1024 --rpc "%RPC%" --no-display-prompt --temp 0.7 --repeat-penalty 1.1 -ngl 0 > "C:\Users\marti\Desktop\Cluster\code\mtp_test_150.out" 2> "C:\Users\marti\Desktop\Cluster\code\mtp_test_150.err"
echo EXIT=%ERRORLEVEL% >> "C:\Users\marti\Desktop\Cluster\code\mtp_test_150.err"
