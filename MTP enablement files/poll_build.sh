#!/bin/bash
echo "=== proc ==="
pgrep -af build_mtp | head
echo "nvcc count: $(pgrep -c nvcc)"
echo "=== log tail ==="
tail -n 20 /home/jetson/mtp_build.log
echo "=== log mtime ==="
stat -c %y /home/jetson/mtp_build.log
