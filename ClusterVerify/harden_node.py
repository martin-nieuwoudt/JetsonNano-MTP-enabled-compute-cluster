import paramiko
import sys

IP = sys.argv[1] if len(sys.argv) > 1 else "192.168.50.150"
KEY = r"C:\Users\marti\.ssh\id_ed25519"
USER = "jetson"

def connect():
    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(IP, username=USER, key_filename=KEY, timeout=10)
    return c

def run(c, cmd, timeout=40):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode()
    err = stderr.read().decode()
    return out, err

print(f">>> HARDEN {IP}")

# ---- Step 1: SSH key-only (PasswordAuthentication no) ----
c = connect()
sshd_cmd = r"""
set +e
echo "== current effective password auth =="
sudo sshd -T 2>/dev/null | grep -i '^passwordauthentication'
DROPIN=/etc/ssh/sshd_config.d/99-cluster-hardening.conf
if grep -q '^Include /etc/ssh/sshd_config.d' /etc/ssh/sshd_config; then
  sudo tee "$DROPIN" >/dev/null <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no
PermitRootLogin no
EOF
  echo "WROTE drop-in $DROPIN"
else
  if ! sudo grep -q '^PasswordAuthentication no' /etc/ssh/sshd_config; then
    printf '\n# Cluster hardening (baked via node_prep)\nPasswordAuthentication no\nKbdInteractiveAuthentication no\nChallengeResponseAuthentication no\nPermitRootLogin no\n' | sudo tee -a /etc/ssh/sshd_config >/dev/null
  fi
  echo "APPENDED to main /etc/ssh/sshd_config"
fi
sudo sshd -t && echo "SSHD_CONFIG_VALID"
sudo systemctl restart ssh
sleep 1
echo "== effective password auth after restart =="
sudo sshd -T 2>/dev/null | grep -i '^passwordauthentication'
"""
out, err = run(c, sshd_cmd)
print(out)
if err.strip():
    print("ERR", err)
c.close()

# ---- Step 2: verify key auth still works (reconnect) ----
print(">>> verify key auth still works after restart...")
c = connect()
out, err = run(c, "echo KEY_AUTH_OK; sudo sshd -T 2>/dev/null | grep -i '^passwordauthentication'")
print(out)
if err.strip():
    print("ERR", err)
c.close()

# ---- Step 3: firewall ----
print(">>> enabling ufw (allow 22,50052,2049,111)...")
c = connect()
ufw_cmd = (
    "sudo ufw allow 22/tcp; "
    "sudo ufw allow 50052/tcp; "
    "sudo ufw allow 2049/tcp; "
    "sudo ufw allow 111/tcp; "
    "sudo ufw --force enable; "
    "echo '== ufw status =='; sudo ufw status verbose"
)
out, err = run(c, ufw_cmd, timeout=60)
print(out)
if err.strip():
    print("ERR", err)
c.close()

# ---- Step 4: final verification ----
print(">>> final verification...")
c = connect()
out, err = run(c, "echo '== ufw =='; sudo ufw status verbose | head -20; echo '== sshd pw =='; sudo sshd -T 2>/dev/null | grep -i '^passwordauthentication'")
print(out)
if err.strip():
    print("ERR", err)
c.close()
print(">>> DONE")
