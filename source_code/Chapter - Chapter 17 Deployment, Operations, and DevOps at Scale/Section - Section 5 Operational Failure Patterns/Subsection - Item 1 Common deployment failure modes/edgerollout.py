#!/usr/bin/env python3
# Progressive rollout controller: polls health, evaluates gates, triggers API actions.
import asyncio, aiohttp, math
API_TRIGGER_URL = "https://orchestrator.example/api/v1/rollout"  # orchestrator API
REGION_DEVICES = {"eu": ["10.0.1.2","10.0.1.3"], "us": ["10.1.1.2"]}  # device endpoints

async def check_device(session, host):
    try:
        async with session.get(f"https://{host}/health", timeout=5) as r:
            data = await r.json()
            return data.get("status") == "ok"
    except Exception:
        return False

async def evaluate_region(region, devices, threshold=0.95):
    async with aiohttp.ClientSession() as s:
        results = await asyncio.gather(*(check_device(s,d) for d in devices))
    success = sum(1 for r in results if r)
    ratio = success / len(devices)
    return ratio >= threshold, ratio

async def trigger_action(action, region):
    # action: "continue", "rollback"; POST to orchestrator with auth (omitted)
    async with aiohttp.ClientSession() as s:
        await s.post(API_TRIGGER_URL, json={"action": action, "region": region})

async def controller():
    for region, devices in REGION_DEVICES.items():
        ok, ratio = await evaluate_region(region, devices)
        print(region, "ok" if ok else "blocked", f"{ratio:.2f}")
        if not ok:
            await trigger_action("rollback", region)
            return
        await trigger_action("continue", region)

if __name__ == "__main__":
    asyncio.run(controller())