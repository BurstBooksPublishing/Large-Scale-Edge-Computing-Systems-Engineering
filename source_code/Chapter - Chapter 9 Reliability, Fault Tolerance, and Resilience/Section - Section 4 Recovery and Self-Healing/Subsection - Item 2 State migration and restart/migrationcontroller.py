#!/usr/bin/env python3
"""
Minimal, production-oriented controller to checkpoint a containerd/runc container,
transfer checkpoint artifacts over SSH, and restore on the target node.
Requires: runc (with criu), paramiko, TLS/SSH keys managed by operator.
"""
import subprocess, os, sys
import paramiko
from pathlib import Path

SRC_CONTAINER = os.environ.get("SRC_CONTAINER")  # container id
CHECKPOINT_NAME = "migration_ckpt"
CHECKPOINT_DIR = Path("/var/lib/checkpoints")   # secure dir, operator-managed
TARGET_HOST = os.environ.get("TARGET_HOST")
TARGET_USER = "edgeadmin"
SSH_KEY = os.environ.get("SSH_KEY_PATH", "/etc/edge/ssh_key")

def run(cmd):
    subprocess.run(cmd, check=True)

def create_checkpoint(cid):
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    run(["runc", "checkpoint", "--image-path", str(CHECKPOINT_DIR), "--work-path",
         str(CHECKPOINT_DIR), "--leave-running=false", cid])
    # ensures consistent stop-and-copy. Use --leave-running=true for pre-copy variants.

def sftp_transfer(artifact_dir, host, user, key_path):
    key = paramiko.RSAKey.from_private_key_file(key_path)
    client = paramiko.SSHClient(); client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, username=user, pkey=key, timeout=10)
    sftp = client.open_sftp()
    for p in artifact_dir.iterdir():
        if p.is_file():
            # atomic upload to temporary name then rename
            tmp = f"{p.name}.part"
            sftp.put(str(p), tmp)
            sftp.rename(tmp, p.name)
    sftp.close(); client.close()

def remote_restore(host, user, key_path, remote_dir, cid):
    key = paramiko.RSAKey.from_private_key_file(key_path)
    client = paramiko.SSHClient(); client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, username=user, pkey=key, timeout=10)
    # recreate container and restore; operator must ensure image and config exist on target.
    cmd = f"sudo runc restore --image-path {remote_dir} --work-path {remote_dir} {cid}"
    stdin, stdout, stderr = client.exec_command(cmd, timeout=60)
    exit_status = stdout.channel.recv_exit_status()
    client.close()
    if exit_status != 0:
        raise RuntimeError("remote restore failed")

def main():
    if not SRC_CONTAINER or not TARGET_HOST:
        print("SRC_CONTAINER and TARGET_HOST env vars required", file=sys.stderr); sys.exit(2)
    create_checkpoint(SRC_CONTAINER)
    sftp_transfer(CHECKPOINT_DIR, TARGET_HOST, TARGET_USER, SSH_KEY)
    remote_restore(TARGET_HOST, TARGET_USER, SSH_KEY, "/var/lib/checkpoints", SRC_CONTAINER)

if __name__ == "__main__":
    main()