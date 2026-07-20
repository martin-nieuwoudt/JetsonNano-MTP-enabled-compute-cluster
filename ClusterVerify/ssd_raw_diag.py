import paramiko, sys

KEY = r"C:\Users\marti\.ssh\id_ed25519"
HOST = "192.168.50.150"
USER = "jetson"

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, username=USER, key_filename=KEY, timeout=5)

def run(cmd):
    _, o, e = ssh.exec_command(cmd)
    out = o.read().decode()
    err = e.read().decode()
    return out, err

print("=== RAW df -T -B1 /mnt/ssd ===")
out, err = run("df -T -B1 /mnt/ssd 2>/dev/null")
print(repr(out))
print("ERR:", repr(err))

print("=== df -h /mnt/ssd ===")
out, _ = run("df -h /mnt/ssd 2>/dev/null")
print(out)

print("=== /proc/mounts ssd line ===")
out, _ = run("awk '$2==\"/mnt/ssd\" {print}' /proc/mounts")
print(out)

print("=== smb.conf [ssd] block ===")
out, _ = run("grep -A8 '\\[ssd\\]' /etc/samba/smb.conf")
print(out)

print("=== ls -la /mnt/ssd ===")
out, _ = run("ls -la /mnt/ssd")
print(out)

print("=== du -sh /mnt/ssd/* (model sizes) ===")
out, _ = run("du -sh /mnt/ssd/* 2>/dev/null")
print(out)

ssh.close()
