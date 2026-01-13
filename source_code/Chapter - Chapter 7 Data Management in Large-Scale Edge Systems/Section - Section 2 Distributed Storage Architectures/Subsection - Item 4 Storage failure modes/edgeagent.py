#!/usr/bin/env python3
"""Edge storage health agent: detect failing devices and proactively replicate objects."""

import hashlib, logging, os, shlex, shutil, sqlite3, subprocess, time
from pathlib import Path
from typing import List

# Config (replace with YAML loader in production)
PEERS = ["edge-peer-1.example.com:/data/replicas", "edge-peer-2.example.com:/data/replicas"]
DATA_DIR = Path("/var/lib/edge_data")
DB_PATH = "/var/lib/edge_meta.sqlite"
SMARTCTL = "/usr/sbin/smartctl"

logging.basicConfig(level=logging.INFO)

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1<<16), b""):
            h.update(chunk)
    return h.hexdigest()

def smart_good(device: str) -> bool:
    try:
        out = subprocess.check_output([SMARTCTL, "-H", device], stderr=subprocess.STDOUT)
        return b"PASSED" in out
    except subprocess.CalledProcessError as e:
        logging.warning("smartctl failed: %s", e)
        return False

def get_tracked_objects(conn) -> List[tuple]:
    cur = conn.execute("SELECT path,sha256 FROM objects")
    return cur.fetchall()

def replicate_to_peer(src: Path, peer: str) -> bool:
    # Use rsync over SSH; rely on SSH keys and directory permissions
    cmd = ["rsync", "-a", str(src), peer]
    try:
        subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        return True
    except subprocess.CalledProcessError:
        return False

def main():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    while True:
        # Device health check example on /dev/nvme0n1
        if not smart_good("/dev/nvme0n1"):
            logging.error("Device health degraded on /dev/nvme0n1; triggering proactive replication")
            for path, expected in get_tracked_objects(conn):
                p = Path(path)
                if not p.exists(): continue
                # verify checksum and push to peers
                actual = sha256_file(p)
                if actual != expected:
                    logging.warning("Checksum mismatch %s; scheduling replication", p)
                for peer in PEERS:
                    if replicate_to_peer(p, peer):
                        logging.info("Replicated %s to %s", p, peer)
                        break
                    else:
                        logging.warning("Replication to %s failed, retrying later", peer)
        # periodic verification sweep
        for path, expected in get_tracked_objects(conn):
            p = Path(path)
            if not p.exists(): continue
            if sha256_file(p) != expected:
                logging.warning("Detected corrupt object %s", p)
                for peer in PEERS:
                    if replicate_to_peer(p, peer):
                        logging.info("Restored %s from peer %s", p, peer)
                        break
        time.sleep(300)  # 5 minutes
if __name__ == "__main__":
    main()