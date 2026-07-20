#!/bin/bash
ssh -o BatchMode=yes jetson@192.168.50.150 'grep -n -i "error:" /home/jetson/mtp_build.log | tail -40'
