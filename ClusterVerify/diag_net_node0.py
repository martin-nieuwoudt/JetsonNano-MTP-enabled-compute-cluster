import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.50.150', username='jetson', key_filename=r'C:\Users\marti\.ssh\id_ed25519', timeout=10)
cmd = (
    "echo '== default route =='; "
    "ip route show default; "
    "echo '== DNS resolver =='; "
    "systemd-resolve --status 2>/dev/null | grep -A2 'DNS Servers' || cat /etc/resolv.conf | grep nameserver; "
    "echo '== resolve external =='; "
    "getent hosts archive.ubuntu.com || echo 'DNS FAIL'; "
    "echo '== ping gateway =='; "
    "ping -c2 -W3 192.168.50.1 >/dev/null 2>&1 && echo 'GW OK' || echo 'GW FAIL'; "
    "echo '== ping external IP (8.8.8.8) =='; "
    "ping -c2 -W3 8.8.8.8 >/dev/null 2>&1 && echo 'EXT IP OK' || echo 'EXT IP FAIL'; "
    "echo '== curl external =='; "
    "curl -sS -m8 -o /dev/null -w '%{http_code}\\n' https://archive.ubuntu.com 2>&1 || echo 'CURL FAIL'"
)
stdin, stdout, stderr = c.exec_command(cmd, timeout=40)
print(stdout.read().decode())
print('ERR', stderr.read().decode())
c.close()
