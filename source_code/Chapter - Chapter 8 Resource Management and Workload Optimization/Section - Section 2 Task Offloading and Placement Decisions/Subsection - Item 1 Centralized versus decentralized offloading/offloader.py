#!/usr/bin/env python3
# Simple decentralized offloader for edge devices.
import asyncio, aiohttp, json, logging, socket, time
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
PEER_PORT = 9000
OFFLOAD_PATH = "/offload"
UTIL_THRESHOLD = 0.75  # local util threshold
DISCOVER_INTERVAL = 5.0

async def get_local_metrics() -> Dict:
    # Replace with psutil or hardware counters on Jetson/ARM
    # Placeholder minimal metrics
    return {"util": 0.6, "free_mem": 120*1024*1024}

async def discover_peers() -> List[str]:
    # Simple UDP multicast discovery (production: mDNS or control-plane registry)
    peers = []
    # multicast discovery omitted for brevity; return configured peers
    return peers

async def measure_rtt(peer: str, timeout=0.5) -> float:
    # Measure TCP connect RTT (approximate)
    start = time.time()
    try:
        reader, writer = await asyncio.open_connection(peer, PEER_PORT, limit=1024)
        writer.close()
        await writer.wait_closed()
        return (time.time() - start)
    except Exception:
        return float('inf')

async def offload_task(session: aiohttp.ClientSession, peer: str, payload: bytes) -> bool:
    # POST task to peer; integrate with container runtime or WASM runtimes in real deployments
    url = f"http://{peer}:{PEER_PORT}{OFFLOAD_PATH}"
    try:
        async with session.post(url, data=payload, timeout=5) as resp:
            return resp.status == 200
    except Exception as e:
        logging.debug("offload failed: %s", e)
        return False

async def decision_loop():
    async with aiohttp.ClientSession() as session:
        while True:
            metrics = await get_local_metrics()
            if metrics["util"] < UTIL_THRESHOLD:
                await asyncio.sleep(1.0)
                continue
            peers = await discover_peers()
            best_peer, best_score = None, float('inf')
            for p in peers:
                rtt = await measure_rtt(p)
                score = rtt  # could add advertised price or capacity
                if score < best_score:
                    best_score, best_peer = score, p
            if best_peer:
                payload = b'{"task":"inference","data":"..."}'
                ok = await offload_task(session, best_peer, payload)
                logging.info("Offloaded to %s success=%s rtt=%.3f", best_peer, ok, best_score)
            else:
                logging.info("No peer available; queueing locally")
            await asyncio.sleep(DISCOVER_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(decision_loop())
    except KeyboardInterrupt:
        pass