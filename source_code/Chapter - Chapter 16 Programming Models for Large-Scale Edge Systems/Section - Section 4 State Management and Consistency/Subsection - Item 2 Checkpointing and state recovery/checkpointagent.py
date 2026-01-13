#!/usr/bin/env python3
import asyncio, tempfile, hashlib, os, shutil, time, logging
import boto3, botocore
from pathlib import Path

# Configurable parameters
STATE_DIR = Path("/var/app/state")        # application state directory
CHECKPOINT_DIR = Path("/var/checkpoints") # local checkpoint staging
S3_BUCKET = "edge-checkpoints"
S3_PREFIX = "site1/device42"
MAX_RETRIES = 5
BACKOFF_BASE = 2.0

logging.basicConfig(level=logging.INFO)

def atomic_snapshot(src: Path, dst_dir: Path) -> Path:
    ts = int(time.time())
    dst_dir.mkdir(parents=True, exist_ok=True)
    tmp = dst_dir / f"chkpt-{ts}.tmp"
    final = dst_dir / f"chkpt-{ts}.tar.gz"
    # create compressed tarball atomically
    shutil.make_archive(str(tmp), 'gztar', root_dir=str(src))
    os.replace(f"{tmp}.tar.gz", final)            # atomic rename on POSIX
    # fsync directory to commit rename
    fd = os.open(str(dst_dir), os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    return final

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1<<20), b""):
            h.update(chunk)
    return h.hexdigest()

async def upload_with_retries(s3_client, key: str, path: Path):
    delay = 1.0
    for attempt in range(1, MAX_RETRIES+1):
        try:
            s3_client.upload_file(str(path), S3_BUCKET, key)
            logging.info("uploaded %s to s3://%s/%s", path.name, S3_BUCKET, key)
            return
        except botocore.exceptions.ClientError as e:
            logging.warning("upload failed attempt %d: %s", attempt, e)
            if attempt == MAX_RETRIES:
                raise
            await asyncio.sleep(delay)
            delay *= BACKOFF_BASE

async def checkpoint_loop(interval_sec: int):
    s3 = boto3.client("s3")     # uses instance credentials or env
    while True:
        start = time.time()
        try:
            chkpt = atomic_snapshot(STATE_DIR, CHECKPOINT_DIR)  # local atomic step
            digest = sha256_file(chkpt)
            key = f"{S3_PREFIX}/{chkpt.name}.sha256"
            # write checksum locally then upload both objects
            with open(f"{chkpt}.sha256", "w") as f:
                f.write(digest)
            await upload_with_retries(s3, f"{S3_PREFIX}/{chkpt.name}", chkpt)
            await upload_with_retries(s3, key, Path(f"{chkpt}.sha256"))
        except Exception as e:
            logging.error("checkpoint failed: %s", e)
        # sleep remaining interval
        elapsed = time.time() - start
        await asyncio.sleep(max(0, interval_sec - elapsed))

if __name__ == "__main__":
    # interval computed from policy or Young/Daly formula
    asyncio.run(checkpoint_loop(interval_sec=2700))