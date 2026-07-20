cd /home/jetson
echo "=== full error context from log ==="
grep -n "fattn-tile-instance-dkq112-dv112\|Error 1\|fatal error\|error:\|undefined\|No such" /home/jetson/mtp_build.log | tail -40
echo ""
echo "=== 40 lines before the fattn error ==="
grep -n "fattn-tile-instance-dkq112-dv112.cu.o] Error 1" /home/jetson/mtp_build.log
