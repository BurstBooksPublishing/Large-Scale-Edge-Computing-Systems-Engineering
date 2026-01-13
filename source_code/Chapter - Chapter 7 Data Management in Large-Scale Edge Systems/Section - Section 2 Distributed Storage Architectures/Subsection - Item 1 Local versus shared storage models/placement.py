#!/usr/bin/env python3
# Production-ready: asyncio event loop, persistent counters, MinIO integration.
import asyncio, time, math
import plyvel                # RocksDB binding; prebuilt on ARM64
from minio import Minio      # S3-compatible client for shared store

DB_PATH = "/var/lib/edge/state_counters"
LOCAL_STORE = "/var/lib/edge/local_store"
MINIO_ENDPOINT = "minio.cluster.local:9000"

# cost profile (tunable by ops)
L_LOC = 0.005    # sec
L_REM = 0.050    # sec
B_COST = 0.002   # sec-equivalent per access
S_COST = 0.0005  # sec-equivalent per second amortized

client = Minio(MINIO_ENDPOINT, access_key="AK", secret_key="SK", secure=False)
db = plyvel.DB(DB_PATH, create_if_missing=True)

def lambda_threshold(l_rem=L_REM, l_loc=L_LOC, b=B_COST, s=S_COST):
    denom = (l_rem - l_loc - b)
    return (s / denom) if denom > 0 else float('inf')

LAMBDA_STAR = lambda_threshold()

async def record_access(key: bytes):
    # increment time-decayed counter (simple exponential decay)
    now = int(time.time())
    raw = db.get(key) or b"0,0"
    count, last = map(int, raw.split(b","))
    dt = now - last if last else 0
    # decay factor per second, tau=300s
    tau = 300.0
    decayed = count * math.exp(-dt / tau)
    decayed += 1.0
    db.put(key, f"{int(decayed)},{now}".encode())

    if decayed > LAMBDA_STAR * tau:   # map to comparable window
        await promote_local(key)

async def promote_local(key: bytes):
    # idempotent: check if present locally, otherwise fetch from MinIO and persist
    local_path = f"{LOCAL_STORE}/{key.decode()}.blob"
    try:
        with open(local_path, "rb"):
            return
    except FileNotFoundError:
        # stream from MinIO and write atomically
        obj = client.get_object("shared-bucket", key.decode())
        with open(local_path + ".tmp", "wb") as f:
            for chunk in obj.stream(32*1024):
                f.write(chunk)
        # atomic rename
        import os
        os.replace(local_path + ".tmp", local_path)

# example hook: called by local HTTP server or SDK on each data read
# asyncio.run(record_access(b"sensor_42_stream"))