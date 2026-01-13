# production-ready asyncio cache agent; requires aiohttp, cachetools, aiobloom
import asyncio, aiohttp
from aiohttp import web
from cachetools import LRUCache
from aiobloom import BloomFilter  # compact membership hint

CACHE_CAP = 1000  # object count
PEER_HEALTH_INTERVAL = 5.0

class CacheAgent:
    def __init__(self, peers):
        self.cache = LRUCache(CACHE_CAP)
        self.peers = peers  # list of (host,port)
        self.bloom = BloomFilter(capacity=10000, error_rate=1e-4)
        self.rtt = {p: 0.05 for p in peers}

    async def probe_peers(self):
        while True:
            async with aiohttp.ClientSession() as s:
                for p in list(self.peers):
                    url = f'http://{p}/ping'
                    try:
                        t0 = asyncio.get_event_loop().time()
                        async with s.get(url, timeout=1.0) as r:
                            await r.text()
                        self.rtt[p] = asyncio.get_event_loop().time() - t0
                    except Exception:
                        self.rtt[p] = float('inf')
            await asyncio.sleep(PEER_HEALTH_INTERVAL)

    async def fetch_from_peer(self, peer, key):
        async with aiohttp.ClientSession() as s:
            async with s.get(f'http://{peer}/cache/{key}', timeout=2.0) as r:
                if r.status == 200:
                    data = await r.read()
                    self.cache[key] = data
                    self.bloom.add(key)
                    return data
        return None

    async def handle_get(self, request):
        key = request.match_info['key']
        if key in self.cache:
            return web.Response(body=self.cache[key])
        # peer selection: filter by bloom hint then by RTT
        candidates = [p for p in self.peers if self.rtt.get(p,1e9) < 1.0]
        candidates.sort(key=lambda p: self.rtt.get(p,1e9))
        for p in candidates:
            # ask peer for bloom-superset flag first
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get(f'http://{p}/hint/{key}', timeout=0.5) as h:
                        if h.status != 200: continue
                        if (await h.text()) != '1': continue
                data = await self.fetch_from_peer(p, key)
                if data is not None: return web.Response(body=data)
            except Exception:
                continue
        # fallback to origin
        async with aiohttp.ClientSession() as s:
            async with s.get(f'http://origin.example/cache/{key}', timeout=5.0) as o:
                data = await o.read()
                self.cache[key] = data
                self.bloom.add(key)
                return web.Response(body=data)

app = web.Application()
agent = CacheAgent(peers=['10.0.0.2:8080','10.0.0.3:8080'])
app.add_routes([web.get('/cache/{key}', agent.handle_get)])
# endpoints for hints and ping omitted for brevity

# run probe background task and app
# (deployment should run under systemd or container with healthchecks)