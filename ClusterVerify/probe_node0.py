import socket, paramiko, sys
sys.path.insert(0, r"C:\Users\marti\Desktop\Cluster\code")
from mcp.cluster_config import RPC_PORT, SSH_USER, SSH_KEY_PATH

ip = "192.168.50.150"
s = socket.socket(); s.settimeout(2.0)
r = s.connect_ex((ip, RPC_PORT)); s.close()
print("RPC connect_ex result (0=open):", r)

try:
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username=SSH_USER, key_filename=SSH_KEY_PATH, timeout=3.0)
    _, o, _ = ssh.exec_command("awk '/MemAvailable/{print $2}' /proc/meminfo")
    print("RAM kb:", o.read().decode().strip())
    ssh.close()
except Exception as e:
    print("SSH ERROR:", repr(e))
