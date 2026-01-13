import asyncio, aiohttp, statistics, shutil, psutil, time

MEC_URL = "https://mec.example.local/health"   # ETSI MEC endpoint
DEADLINE_MS = 50
SAMPLES = 5
TIMEOUT = 0.05  # 50 ms

async def probe_mec(session):
    t0 = time.perf_counter()
    try:
        async with session.get(MEC_URL, timeout=TIMEOUT) as r:
            await r.read()
        return (time.perf_counter()-t0)*1000.0
    except asyncio.TimeoutError:
        return None

def local_estimate():
    # conservative local processing time estimate based on CPU utilization
    util = psutil.cpu_percent(interval=0.01)
    base_local_ms = 25.0
    penalty = (util/100.0)*30.0
    return base_local_ms + penalty

async def select_processing():
    async with aiohttp.ClientSession() as sess:
        rtts = []
        for _ in range(SAMPLES):
            r = await probe_mec(sess)
            if r is not None: rtts.append(r)
            await asyncio.sleep(0.01)
        mec_rtt = statistics.mean(rtts) if rtts else float('inf')
        mec_queue_est = 8.0  # from MEC telemetry (ms)
        mec_proc_est = 10.0  # advertised service time (ms)
        sense_ms = 10.0
        local_ms = local_estimate()
        mec_total = sense_ms + mec_rtt + mec_queue_est + mec_proc_est
        local_total = sense_ms + local_ms
        # choose processing with deadline and margin
        if mec_total < DEADLINE_MS and mec_total < local_total:
            return "mec", mec_total
        return "local", local_total

if __name__ == "__main__":
    choice, est = asyncio.run(select_processing())
    print(f"chosen={choice}, est_latency_ms={est:.2f}")