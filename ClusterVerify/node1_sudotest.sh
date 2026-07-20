#!/bin/bash
KEY=/root/.ssh/id_ed25519
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
echo "--- node0 sudo test ---"
ssh $OPTS jetson@192.168.50.150 'sudo -n true && echo NODE0_SUDO_OK || echo NODE0_SUDO_FAIL' 2>&1
echo "--- node1 sudo test ---"
ssh $OPTS jetson@192.168.50.151 'sudo -n true && echo NODE1_SUDO_OK || echo NODE1_SUDO_FAIL' 2>&1
echo DONE
