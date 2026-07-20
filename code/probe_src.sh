#!/usr/bin/env bash
timeout 8 ssh -o BatchMode=yes jetson@192.168.50.155 'echo "--- home ---"; ls /home/jetson/; echo "--- llama.cpp-mtp top ---"; ls /home/jetson/llama.cpp-mtp/; echo "--- build ---"; ls /home/jetson/llama.cpp-mtp/build/' 2>&1
