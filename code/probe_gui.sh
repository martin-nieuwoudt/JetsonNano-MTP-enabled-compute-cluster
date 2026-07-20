#!/usr/bin/env bash
for n in 150 151 152 153 154 155 156 157 158 159 160; do
  ip="192.168.50.$n"
  r=$(timeout 8 ssh -o BatchMode=yes -o ConnectTimeout=5 jetson@$ip 'pgrep -f "Xorg|gdm|lightdm"' 2>/dev/null)
  echo "$ip GUI-pgrep(Xorg|gdm|lightdm) -> ${r:-NONE}"
done
