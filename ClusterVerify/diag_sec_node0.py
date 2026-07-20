import paramiko
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('192.168.50.150', username='jetson',
          key_filename=r'C:\Users\marti\.ssh\id_ed25519', timeout=10)
cmd = (
    "echo '== ufw status =='; sudo ufw status verbose 2>/dev/null || echo 'ufw not installed/runnable'; "
    "echo '== sshd PasswordAuthentication =='; sudo grep -Ri '^\\s*PasswordAuthentication' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/ 2>/dev/null || echo 'not explicitly set (default = yes)'; "
    "echo '== sshd PermitRootLogin =='; sudo grep -Ri '^\\s*PermitRootLogin' /etc/ssh/sshd_config /etc/ssh/sshd_config.d/ 2>/dev/null || echo 'not explicitly set (default = prohibit-password)'; "
    "echo '== jetson pw set? (passwd -S) =='; sudo passwd -S jetson 2>/dev/null; "
    "echo '== rpc-server bind =='; sudo ss -ltnp 2>/dev/null | grep -E '50052|rpc' || echo 'rpc port not visible from ss (may run as jetson)'; "
    "echo '== nfs export =='; sudo cat /etc/exports 2>/dev/null || echo 'no /etc/exports'"
)
stdin, stdout, stderr = c.exec_command(cmd, timeout=40)
print(stdout.read().decode()); print('ERR', stderr.read().decode()); c.close()
