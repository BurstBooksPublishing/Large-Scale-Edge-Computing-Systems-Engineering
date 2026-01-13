#!/usr/bin/env python3
# Adaptive controller: monitors system and instructs local pipeline via REST.
import asyncio, aiohttp, psutil, time, logging
API_ENDPOINT = "http://localhost:8080/api/v1/pipeline/config"  # pipeline reads config
CHECK_INTERVAL = 1.0  # seconds
CPU_HIGH = 0.85
NET_RTT_THRESHOLD = 0.2  # seconds

async def fetch_rtt(session, host="8.8.8.8"):
    start = time.time()
    try:
        async with session.get(f"http://{host}", timeout=0.5):
            pass
    except Exception:
        pass
    return time.time() - start

async def adjust_pipeline(session, cfg):
    # idempotent PUT operation expected by pipeline API
    async with session.put(API_ENDPOINT, json=cfg, timeout=2) as resp:
        resp.raise_for_status()

async def monitor_loop():
    async with aiohttp.ClientSession() as session:
        while True:
            cpu = psutil.cpu_percent(interval=None) / 100.0
            mem = psutil.virtual_memory().percent / 100.0
            rtt = await fetch_rtt(session)
            cfg = {"model": "high", "telemetry": True, "fps": 15}
            # fidelity policy: prefer lower model if CPU high or network poor
            if cpu > CPU_HIGH or rtt > NET_RTT_THRESHOLD:
                cfg["model"] = "mobile"     # lower-cost model
                cfg["telemetry"] = False    # shed telemetry
                cfg["fps"] = 5
            # apply only on change to limit churn
            try:
                await adjust_pipeline(session, cfg)
            except Exception as e:
                logging.warning("config apply failed: %s", e)
            await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(monitor_loop())