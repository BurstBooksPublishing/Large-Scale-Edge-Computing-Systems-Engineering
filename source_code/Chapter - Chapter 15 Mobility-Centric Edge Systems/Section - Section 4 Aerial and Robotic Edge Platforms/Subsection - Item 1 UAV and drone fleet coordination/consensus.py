#!/usr/bin/env python3
# Companion-side decentralized neighbor exchange and position consensus.
import asyncio, json, time, math, socket
from typing import Dict, Tuple

ALPHA = 0.2                  # consensus step
HEARTBEAT = 0.2              # seconds
NEIGHBOR_TIMEOUT = 1.0      # seconds
BIND_ADDR = ("0.0.0.0", 17000)
PEER_PORT = 17000

# Node state
node_id = f"node-{socket.gethostname()}"
pos = (0.0, 0.0)             # replace with local GNSS or VIO pose
neighbors: Dict[str, Tuple[Tuple[float,float], float]] = {}  # id -> (pos, ts)

async def sender(loop):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setblocking(False)
    while True:
        msg = json.dumps({"id": node_id, "pos": pos, "ts": time.time()}).encode()
        # broadcast or send to known peer list (here: simple subnet broadcast)
        sock.sendto(msg, ("", PEER_PORT))
        await asyncio.sleep(HEARTBEAT)

async def receiver(loop):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.bind(BIND_ADDR)
    sock.setblocking(False)
    while True:
        try:
            data, addr = sock.recvfrom(2048)
        except BlockingIOError:
            await asyncio.sleep(0.01)
            continue
        try:
            j = json.loads(data.decode())
            if j["id"] == node_id: continue
            neighbors[j["id"]] = ((float(j["pos"][0]), float(j["pos"][1])), float(j["ts"]))
        except Exception:
            continue

def prune_neighbors():
    now = time.time()
    to_del = [nid for nid,(_,ts) in neighbors.items() if now - ts > NEIGHBOR_TIMEOUT]
    for nid in to_del: neighbors.pop(nid, None)

async def consensus_loop(loop):
    global pos
    while True:
        prune_neighbors()
        if neighbors:
            # equal weighting
            nx = sum(p[0][0] for p in neighbors.values()) / len(neighbors)
            ny = sum(p[0][1] for p in neighbors.values()) / len(neighbors)
            # simple update towards local neighbor average
            pos = (pos[0] + ALPHA*(nx - pos[0]), pos[1] + ALPHA*(ny - pos[1]))
        await asyncio.sleep(HEARTBEAT)

async def main():
    loop = asyncio.get_running_loop()
    await asyncio.gather(sender(loop), receiver(loop), consensus_loop(loop))

if __name__ == "__main__":
    asyncio.run(main())