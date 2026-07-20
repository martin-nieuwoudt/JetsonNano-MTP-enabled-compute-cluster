echo "=== build_mtp.sh ==="; cat /home/jetson/build_mtp.sh 2>/dev/null || echo "MISSING"
echo "=== launch_build.sh ==="; cat /home/jetson/launch_build.sh 2>/dev/null || echo "MISSING"
echo "=== gcc/g++ versions ==="; gcc-9 --version 2>/dev/null | head -1; g++-9 --version 2>/dev/null | head -1; gcc-8 --version 2>/dev/null | head -1
echo "=== nvcc ==="; /usr/local/cuda-10.2/bin/nvcc --version 2>/dev/null | tail -2
