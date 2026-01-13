import sqlite3, uuid, time, requests, random

DB = "/var/lib/edge/idempotency.db"
API = "https://agg.example.com/events"

# initialize persistent local store for idempotency keys and statuses
def init_db():
    with sqlite3.connect(DB) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS uploads(key TEXT PRIMARY KEY, status TEXT, result TEXT, ts INTEGER)")
        conn.commit()

def save_record(key, status, result=None):
    ts = int(time.time())
    with sqlite3.connect(DB) as conn:
        conn.execute("REPLACE INTO uploads VALUES(?,?,?,?)", (key, status, result, ts))
        conn.commit()

def upload_event(payload, max_attempts=5, base_delay=0.5, backoff=2.0):
    key = f"{payload['device_id']}:{payload['seq']}"  # durable idempotency key
    # check persisted outcome to provide at-most-once semantics
    with sqlite3.connect(DB) as conn:
        cur = conn.execute("SELECT status, result FROM uploads WHERE key=?", (key,))
        row = cur.fetchone()
        if row:
            return row[0], row[1]  # already processed

    save_record(key, "pending")
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        try:
            headers = {"Idempotency-Key": key}
            r = requests.post(API, json=payload, headers=headers, timeout=5.0)
            if r.status_code in (200,201,202):
                save_record(key, "ok", r.text)
                return "ok", r.text
            # server may indicate duplicate via 409 or custom code; treat as success if server says so
            if r.status_code == 409:
                save_record(key, "ok", r.text)
                return "ok", r.text
        except requests.RequestException:
            pass
        # jittered exponential backoff to avoid synchronized retries
        jitter = random.uniform(0, base_delay)
        sleep_time = base_delay * (backoff ** (attempt-1)) + jitter
        time.sleep(sleep_time)
    save_record(key, "failed")
    return "failed", None

# example usage
if __name__ == "__main__":
    init_db()
    payload = {"device_id": "dev123", "seq": 42, "value": 0.78}
    status, result = upload_event(payload)
    print(status)