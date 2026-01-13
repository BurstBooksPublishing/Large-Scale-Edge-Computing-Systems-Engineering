# replay_client.py
import asyncio, aiohttp, csv, math, random, ssl, time
from datetime import datetime, timezone
from prometheus_client import start_http_server, Counter, Histogram

REQUESTS = Counter('replayed_requests_total', 'Requests replayed')
FAILURES = Counter('replay_failures_total', 'Failed requests')
LATENCY = Histogram('replay_request_latency_seconds', 'Request latency')

# exponential backoff retry
async def do_request(session, url, data, timeout):
    backoff, attempts = 0.1, 0
    while attempts < 5:
        try:
            start = time.monotonic()
            async with session.post(url, json=data, timeout=timeout) as resp:
                await resp.text()
                LATENCY.observe(time.monotonic() - start)
                REQUESTS.inc()
                return True
        except Exception:
            attempts += 1
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 2.0)
    FAILURES.inc()
    return False

async def replay_trace(csv_path, url, speed=1.0, jitter_std=0.0,
                       concurrency=50, tls_verify=True):
    ssl_ctx = ssl.create_default_context() if tls_verify else False
    semaphore = asyncio.Semaphore(concurrency)
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as session:
        tasks = []
        with open(csv_path) as f:
            reader = csv.DictReader(f)
            # parse first timestamp to anchor
            rows = list(reader)
            t0 = datetime.fromisoformat(rows[0]['timestamp']).timestamp()
            start_wall = time.monotonic()
            for r in rows:
                t_i = datetime.fromisoformat(r['timestamp']).timestamp()
                # time-warp with jitter
                delta = (t_i - t0) / speed + random.gauss(0, jitter_std)
                scheduled = start_wall + delta
                data = {'payload': r['payload'], 'source': r.get('source')}
                async def worker(sched, d):
                    await asyncio.sleep(max(0, sched - time.monotonic()))
                    async with semaphore:
                        await do_request(session, url, d, timeout=10)
                tasks.append(asyncio.create_task(worker(scheduled, data)))
        await asyncio.gather(*tasks)

if __name__ == '__main__':
    start_http_server(8000)  # expose Prometheus metrics
    import sys
    path, target = sys.argv[1], sys.argv[2]  # e.g., ./trace.csv https://edge.local/api
    asyncio.run(replay_trace(path, target, speed=2.0, jitter_std=0.005))