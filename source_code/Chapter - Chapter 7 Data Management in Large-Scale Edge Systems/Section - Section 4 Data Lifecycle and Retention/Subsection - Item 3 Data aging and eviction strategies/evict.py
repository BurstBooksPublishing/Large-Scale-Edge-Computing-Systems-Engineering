#!/usr/bin/env python3
# Eviction daemon: background worker for TTL + LFU eviction.
import sqlite3, os, time, heapq
from collections import defaultdict

DB_PATH = "/var/lib/edge_metadata/meta.db"    # SQLite metadata
BLOB_DIR = "/var/lib/edge_data/blobs"
HIGH_WATER = 0.85
LOW_WATER = 0.65
MU = 1e-6  # storage holding cost weight

def init_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("CREATE TABLE IF NOT EXISTS items(id TEXT PRIMARY KEY,size INTEGER,last_access REAL,freq INTEGER,priority INTEGER,ttl REAL)")
    conn.commit()
    return conn

def current_usage():
    st = os.statvfs(BLOB_DIR)
    used = (st.f_blocks - st.f_bfree) * st.f_frsize
    total = st.f_blocks * st.f_frsize
    return used/total

def score_row(row):
    _id,size,last_access,freq,priority,ttl = row
    age = time.time() - last_access
    # p_i approximated by frequency and TTL (older TTL => lower p)
    p_est = freq / (1 + age) if ttl <= 0 or time.time() < ttl else freq*0.5/(1+age)
    retrieval_cost = 0.1 + 1.0*(size/1e6)  # heuristic: base plus proportional to size
    return (_id, (p_est*retrieval_cost) / (size + 1), size, priority)

def evict_loop():
    conn = init_db()
    cur = conn.cursor()
    while True:
        usage = current_usage()
        if usage < HIGH_WATER:
            time.sleep(5)
            continue
        # load metadata; for large catalogs page this
        cur.execute("SELECT id,size,last_access,freq,priority,ttl FROM items")
        rows = cur.fetchall()
        heap = []
        for r in rows:
            _id,val,size,priority = score_row(r)
            # lower value = better candidate for eviction; factor in priority
            heapq.heappush(heap,(val + 0.1*priority, _id, size))
        freed = 0
        target_free = (usage - LOW_WATER) * os.statvfs(BLOB_DIR).f_blocks * os.statvfs(BLOB_DIR).f_frsize
        while heap and freed < target_free:
            _, _id, size = heapq.heappop(heap)
            blob_path = os.path.join(BLOB_DIR, _id)
            try:
                os.remove(blob_path)  # atomic on local FS
            except FileNotFoundError:
                pass
            cur.execute("DELETE FROM items WHERE id=?", (_id,))
            freed += size
        conn.commit()
        time.sleep(1)

if __name__ == "__main__":
    evict_loop()