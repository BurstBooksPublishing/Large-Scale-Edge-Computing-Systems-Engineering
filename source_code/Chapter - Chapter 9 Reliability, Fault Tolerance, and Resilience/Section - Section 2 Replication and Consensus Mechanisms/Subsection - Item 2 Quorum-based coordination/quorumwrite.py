import asyncio
import aiohttp
from typing import List

# Configure endpoints and quorum size
REPLICAS: List[str] = ["https://node1.local:8443","https://node2.local:8443","https://node3.local:8443"]
W = 2
TIMEOUT = 2.0
RETRY_BACKOFF = 0.5

async def send_write(session, url, key, value):
    # Application API: PUT /kv/{key} with JSON payload; server must return 200 on durable ack
    async with session.put(f"{url}/kv/{key}", json={"value": value}, timeout=TIMEOUT) as resp:
        return resp.status == 200

async def quorum_write(key: str, value: str):
    ssl_ctx = aiohttp.Fingerprint(b"")  # placeholder: set proper TLS context/certs
    connector = aiohttp.TCPConnector(ssl=False)  # production: construct ssl.SSLContext
    async with aiohttp.ClientSession(connector=connector) as session:
        pending = [asyncio.create_task(send_write(session, u, key, value)) for u in REPLICAS]
        acks = 0
        for task in asyncio.as_completed(pending, timeout=TIMEOUT+RETRY_BACKOFF*len(REPLICAS)):
            try:
                ok = await task
            except Exception:
                ok = False
            if ok:
                acks += 1
                if acks >= W:
                    # Cancel remaining tasks to reduce network/load
                    for t in pending:
                        if not t.done():
                            t.cancel()
                    return True
        # Optionally retry with exponential backoff
        await asyncio.sleep(RETRY_BACKOFF)
        return False

# Usage: asyncio.run(quorum_write("device42/state", "running"))