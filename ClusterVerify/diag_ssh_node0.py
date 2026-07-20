import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.50.150', username='jetson', key_filename=r'C:\Users\marti\.ssh\id_ed25519', timeout=10)
cmd = (
    "echo '== sshd listening? =='; "
    "ss -ltnp 2>/dev/null | grep -E ':22|ssh' || echo 'NOT LISTENING'; "
    "echo '== service =='; "
    "systemctl is-active ssh 2>/dev/null; systemctl is-active sshd 2>/dev/null; "
    "echo '== recent auth.log =='; "
    "sudo tail -15 /var/log/auth.log 2>/dev/null || sudo tail -15 /var/log/secure 2>/dev/null || echo 'no auth log'; "
    "echo '== host keys =='; "
    "ls -la /etc/ssh/ 2>/dev/null | grep host_key || echo 'NO HOST KEYS'"
)
stdin, stdout, stderr = c.exec_command(cmd, timeout=30)
print(stdout.read().decode())
print('ERR', stderr.read().decode())
c.close()
