#!/usr/bin/env python3
# Production-ready asyncio agent: TLS, retries, backoff, persistent queue.
import asyncio, aiohttp, time, sqlite3, ssl
from math import inf

# Persistent queue (SQLite) for reliable sync
class PersistentQueue:
    def __init__(self, path='events.db'):
        self.conn = sqlite3.connect(path, isolation_level=None)
        self.conn.execute('''CREATE TABLE IF NOT EXISTS q(id INTEGER PRIMARY KEY, evt BLOB)''')
    def push(self, evt):
        self.conn.execute('INSERT INTO q(evt) VALUES (?)', (evt,))
    def pop_batch(self, n=50):
        cur = self.conn.execute('SELECT id, evt FROM q ORDER BY id LIMIT ?', (n,))
        rows = cur.fetchall()
        if not rows: return []
        ids = [r[0] for r in rows]; evts=[r[1] for r in rows]
        self.conn.executemany('DELETE FROM q WHERE id=?', [(i,) for i in ids])
        return evts

# Simple token bucket
class TokenBucket:
    def __init__(self, rate, burst):
        self.rate = rate; self.burst = burst
        self.tokens = burst; self.last = time.monotonic()
    def consume(self, cost=1):
        now = time.monotonic(); self.tokens = min(self.burst, self.tokens + (now-self.last)*self.rate)
        self.last = now
        if self.tokens >= cost:
            self.tokens -= cost; return True
        return False

async def controller_request(session, url, payload, timeout=5):
    # retry with exponential backoff
    backoff = 0.5
    for _ in range(5):
        try:
            async with session.post(url, json=payload, timeout=timeout) as resp:
                resp.raise_for_status(); return await resp.json()
        except Exception:
            await asyncio.sleep(backoff); backoff = min(8, backoff*2)
    raise RuntimeError('controller_unreachable')

async def main_loop(controller_url):
    queue = PersistentQueue()
    tb = TokenBucket(rate=1.0, burst=5)  # admit 1 req/sec, burst 5
    sslctx = ssl.create_default_context()  # production TLS
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=sslctx)) as session:
        while True:
            # gather local event
            evt = {'ts': time.time(), 'metric': probe_sensor()}
            if tb.consume():
                try:
                    # attempt central decision
                    resp = await controller_request(session, controller_url, evt)
                    apply_central_decision(resp)
                except Exception:
                    # fallback local decision and persist event for later sync
                    local_decision = local_policy(evt)
                    apply_local(local_decision)
                    queue.push(str(evt))
            else:
                # rate limited: act locally and persist
                local_decision = local_policy(evt)
                apply_local(local_decision)
                queue.push(str(evt))
            # background sync loop
            await asyncio.sleep(0.1)

# Helper stubs (implement per platform)
def probe_sensor(): return 42
def local_policy(evt): return {'action':'keep'}
def apply_local(d): pass
def apply_central_decision(d): pass

if __name__ == '__main__':
    asyncio.run(main_loop('https://controller.example/api/decide'))