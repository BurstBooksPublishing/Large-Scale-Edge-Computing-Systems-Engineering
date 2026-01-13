#!/usr/bin/env python3
# Minimal dependencies: psutil, aiohttp
import asyncio
import math
import os
import time
import psutil
import aiohttp

REPORT_URL = "https://controller.example.local/api/v1/health"
NODE_ID = os.environ.get("NODE_ID", "edge-001")
CHECK_INTERVAL = 5.0  # seconds
MAX_BACKOFF = 300.0   # seconds

async def sample_hardware():
    # CPU temp via sysfs (Linux); fallback to 0 if not present
    temp = None
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            temp = int(f.read().strip()) / 1000.0
    except Exception:
        temp = psutil.sensors_temperatures().get("coretemp", [{}])[0].get("current", 0.0)
    mem = psutil.virtual_memory().percent
    cpu = psutil.cpu_percent(interval=None)
    return {"cpu_temp": temp, "cpu_pct": cpu, "mem_pct": mem}

async def sample_process(proc_name="app_service"):
    # Check that a named process is running
    for p in psutil.process_iter(["name", "cmdline", "status"]):
        try:
            if proc_name in " ".join(p.info.get("cmdline", []) + [p.info.get("name","")]):
                return {"proc_status": p.info["status"], "pid": p.pid}
        except Exception:
            continue
    return {"proc_status": "missing", "pid": None}

async def ping_latency(host="8.8.8.8"):
    # Simple TCP connect measurement to avoid raw ICMP privileges
    start = time.time()
    try:
        reader, writer = await asyncio.open_connection(host, 53)
        writer.close()
        await writer.wait_closed()
        return max(0.0, (time.time() - start) * 1000.0)
    except Exception:
        return float("inf")

def composite_score(samples):
    # Normalize metrics and compute conservative health score [0,1]
    cpu = min(100.0, samples["cpu_pct"]) / 100.0
    mem = min(100.0, samples["mem_pct"]) / 100.0
    temp = min(100.0, max(20.0, samples["cpu_temp"]))  # clamp
    temp_norm = (temp - 20.0) / 80.0
    proc_ok = 1.0 if samples["proc_status"] != "missing" else 0.0
    rtt = samples["rtt_ms"]
    net_ok = 0.0 if rtt == float("inf") else max(0.0, 1.0 - min(rtt,1000.0)/1000.0)
    # lower of available resources dominates
    return min(proc_ok, 1.0 - max(cpu, mem, temp_norm, 1.0 - net_ok))

async def report(session, payload):
    # Robust HTTP POST with exponential backoff
    backoff = 1.0
    while True:
        try:
            async with session.post(REPORT_URL, json=payload, timeout=10) as resp:
                if resp.status < 300:
                    return await resp.json()
                # treat server errors as retryable
        except Exception:
            pass
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, MAX_BACKOFF)

async def monitor_loop():
    async with aiohttp.ClientSession() as session:
        while True:
            hw = await sample_hardware()
            proc = await sample_process("app_service")
            rtt = await ping_latency("gateway.local")
            samples = {**hw, **proc, "rtt_ms": rtt}
            score = composite_score(samples)
            payload = {"node": NODE_ID, "timestamp": time.time(), "score": score, "samples": samples}
            # fire-and-forget reporting but with internal retry
            asyncio.create_task(report(session, payload))
            # systemd notify can be integrated here if available
            await asyncio.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    asyncio.run(monitor_loop())