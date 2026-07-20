#!/bin/bash
# Make the [ssd] share on node0 guest-accessible (no password) for the private LAN.
# This is safe in the user's context: single-user private network, no external exposure.
OPTS="-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -o ConnectTimeout=8 -o BatchMode=yes"
N0=jetson@192.168.50.150

echo "=== rewrite [ssd] share as guest ok + map to guest ==="
ssh $OPTS $N0 'sudo bash -c "cat > /etc/samba/smb.conf <<EOF
[global]
   workgroup = WORKGROUP
   server string = %h server (Samba, Ubuntu)
   log file = /var/log/samba/log.%m
   max log size = 1000
   logging = file
   panic action = /usr/share/samba/panic-action %d
   server role = standalone server
   obey pam restrictions = yes
   unix password sync = yes
   passwd program = /usr/bin/passwd %u
   passwd chat = *Enter\snew\s*\spassword:* %n\n *Retype\snew\s*\spassword:* %n\n *password\supdated\ssuccessfully* .
   pam password change = yes
   map to guest = bad user
   usershare allow guests = yes

[printers]
   comment = All Printers
   browseable = no
   path = /var/spool/samba
   printable = yes
   guest ok = no
   read only = yes
   create mask = 0700

[print\$]
   comment = Printer Drivers
   path = /var/lib/samba/printers
   browseable = yes
   read only = yes
   guest ok = no

[ssd]
   comment = node0 SSD shared storage (guest, private LAN)
   path = /mnt/ssd
   browseable = yes
   read only = no
   guest ok = yes
   force user = jetson
   create mask = 0644
   directory mask = 0755
EOF
"'
echo "=== restart smbd/nmbd ==="
ssh $OPTS $N0 'sudo systemctl restart smbd nmbd 2>&1; systemctl is-active smbd' 2>&1
echo DONE
