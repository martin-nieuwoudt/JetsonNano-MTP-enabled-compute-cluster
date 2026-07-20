#!/bin/bash
ssh -i /home/marti/.ssh/id_ed25519 -o BatchMode=yes -o StrictHostKeyChecking=no jetson@192.168.50.150 \
  "journalctl -u llama-rpc.service --since '2026-07-14 17:05:00' --no-pager 2>/dev/null | head -45"
