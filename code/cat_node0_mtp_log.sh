#!/bin/bash
# cat_node0_mtp_log.sh - dump the node0 MTP build log
ssh -o BatchMode=yes -o ConnectTimeout=15 -o StrictHostKeyChecking=no jetson@192.168.50.150 'cat /tmp/node0_mtp_build.log'
