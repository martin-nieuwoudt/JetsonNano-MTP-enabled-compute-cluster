$ErrorActionPreference = 'Stop'
$key = 'C:\Users\marti\.ssh\id_ed25519'
$remote = 'jetson@192.168.50.150'
$opts = @('-o', 'StrictHostKeyChecking=no', '-o', 'UserKnownHostsFile=/dev/null')
ssh -i $key @opts $remote 'echo SSH_OK; echo "--- df /mnt/ssd ---"; df -h /mnt/ssd 2>/dev/null || echo NO_SSD_MOUNT; echo "--- models dir ---"; ls -la /mnt/ssd/models 2>/dev/null || echo NO_MODELS_DIR; mkdir -p /mnt/ssd/models && echo MODELS_DIR_READY'
