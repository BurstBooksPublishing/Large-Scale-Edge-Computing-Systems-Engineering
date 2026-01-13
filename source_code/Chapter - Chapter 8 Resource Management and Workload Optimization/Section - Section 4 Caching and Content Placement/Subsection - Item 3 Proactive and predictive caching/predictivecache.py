#!/usr/bin/env python3
# Minimal production-ready predictive prefetch agent.
import asyncio, aiohttp, sqlite3, os, time
from paho.mqtt import client as mqtt

CACHE_DIR = "/var/cache/edge_prefetch"  # persisted cache dir
DB_PATH = os.path.join(CACHE_DIR, "meta.db")
BUDGET_BYTES = 50 * 1024 * 1024  # prefetch byte budget
EWMA_ALPHA = 0.3
PREFETCH_WINDOW = 30  # seconds

os.makedirs(CACHE_DIR, exist_ok=True)
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.execute("CREATE TABLE IF NOT EXISTS items(key TEXT PRIMARY KEY, score REAL, size INT, atime REAL)")
conn.commit()

def ewma_update(old, obs):
    return EWMA_ALPHA*obs + (1-EWMA_ALPHA)*old if old is not None else obs

# MQTT callback updates EWMA scores from cooperative aggregator.
def on_mqtt_message(client, userdata, msg):
    # payload: "key,count" where count is observed requests in last window
    try:
        key, cnt = msg.payload.decode().split(",")
        cnt = float(cnt)
        cur = conn.execute("SELECT score FROM items WHERE key=?", (key,)).fetchone()
        cur_score = cur[0] if cur else None
        new_score = ewma_update(cur_score, cnt)
        if cur:
            conn.execute("UPDATE items SET score=? WHERE key=?", (new_score, key))
        else:
            conn.execute("INSERT INTO items(key,score,size,atime) VALUES(?,?,?,?)",
                         (key, new_score, 0, time.time()))
        conn.commit()
    except Exception:
        pass

async def prefetch_loop():
    async with aiohttp.ClientSession() as sess:
        while True:
            # select candidates ordered by density score/size
            rows = conn.execute("SELECT key,score,size FROM items WHERE score>0 ORDER BY score DESC").fetchall()
            budget = BUDGET_BYTES
            for key, score, size in rows:
                if size and size > budget:
                    continue
                p_hat = 1 - pow(0.5, score)  # map EWMA to probability
                # simple cost model: prefetch if p*C_miss > C_pf -> here C_miss ~ 1000ms, C_pf ~ size/ (bandwidth)
                C_miss = 0.5  # seconds saved if local
                C_pf = (size or 1024) / (1e6)  # seconds to download at 1 MB/s
                if p_hat * C_miss > C_pf and budget > (size or 1024):
                    url = f"https://origin.example/{key}"
                    try:
                        async with sess.get(url, timeout=10) as resp:
                            if resp.status == 200:
                                data = await resp.read()
                                path = os.path.join(CACHE_DIR, key.replace("/","_"))
                                with open(path, "wb") as f:
                                    f.write(data)
                                sz = len(data)
                                conn.execute("UPDATE items SET size=?,atime=? WHERE key=?", (sz, time.time(), key))
                                conn.commit()
                                budget -= sz
                    except Exception:
                        continue
            await asyncio.sleep(PREFETCH_WINDOW)

def start_mqtt_and_loop():
    client = mqtt.Client()
    client.on_message = on_mqtt_message
    client.connect("mqtt-broker.local", 1883, 60)
    client.subscribe("popularity/updates")
    client.loop_start()
    asyncio.run(prefetch_loop())

if __name__ == "__main__":
    start_mqtt_and_loop()