# Minimal delta-gossip agent: asyncio TCP + TLS, persistent state, delta merge.
import asyncio, ssl, json, sqlite3, time, logging
from typing import Dict

DB = "state.db"
PEERS = [("edge-gw.example", 9001)]
TLS_CTX = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)  # configure CA and certs

# persistent store: key -> (value, version)
def init_db():
    conn = sqlite3.connect(DB, isolation_level=None)
    conn.execute("CREATE TABLE IF NOT EXISTS kv (k TEXT PRIMARY KEY, v TEXT, ver INTEGER)")
    return conn

async def send_delta(host, port, tls_ctx, deltas):
    try:
        reader, writer = await asyncio.open_connection(host, port, ssl=tls_ctx)
        payload = json.dumps({"type":"delta","ts":time.time(),"deltas":deltas}).encode()
        writer.write(len(payload).to_bytes(4,'big') + payload)
        await writer.drain()
        # read ack
        size = int.from_bytes(await reader.readexactly(4),'big')
        ack = json.loads(await reader.readexactly(size))
        writer.close(); await writer.wait_closed()
        return ack
    except Exception as e:
        logging.warning("send_delta %s:%d failed: %s", host, port, e)
        return None

def compute_local_deltas(conn, since_version):
    cur = conn.cursor()
    cur.execute("SELECT k, v, ver FROM kv WHERE ver > ?", (since_version,))
    return [{"k":k,"v":v,"ver":ver} for (k,v,ver) in cur.fetchall()]

def apply_delta(conn, deltas):
    cur = conn.cursor()
    for d in deltas:
        cur.execute("SELECT ver FROM kv WHERE k = ?", (d['k'],))
        row = cur.fetchone()
        if (row is None) or (d['ver'] > row[0]):
            cur.execute("REPLACE INTO kv (k,v,ver) VALUES (?,?,?)", (d['k'], d['v'], d['ver']))

async def handle_peer(reader, writer, conn):
    try:
        size = int.from_bytes(await reader.readexactly(4),'big')
        msg = json.loads(await reader.readexactly(size))
        if msg.get("type") == "delta":
            apply_delta(conn, msg.get("deltas",[]))
            ack = json.dumps({"status":"ok","ts":time.time()}).encode()
            writer.write(len(ack).to_bytes(4,'big') + ack); await writer.drain()
    finally:
        writer.close(); await writer.wait_closed()

async def server(loop, host='0.0.0.0', port=9001):
    server = await asyncio.start_server(lambda r,w: handle_peer(r,w,init_db()), host, port, ssl=TLS_CTX)
    async with server:
        await server.serve_forever()

async def periodic_sync(conn):
    last_ver = 0
    while True:
        deltas = compute_local_deltas(conn, last_ver)
        if deltas:
            # best-effort fanout to peers
            await asyncio.gather(*(send_delta(h,p,TLS_CTX,deltas) for (h,p) in PEERS))
            last_ver = max(d['ver'] for d in deltas)
        await asyncio.sleep(5)  # tune for bandwidth/latency
# entry
if __name__ == "__main__":
    conn = init_db()
    loop = asyncio.get_event_loop()
    loop.create_task(server(loop))
    loop.create_task(periodic_sync(conn))
    loop.run_forever()