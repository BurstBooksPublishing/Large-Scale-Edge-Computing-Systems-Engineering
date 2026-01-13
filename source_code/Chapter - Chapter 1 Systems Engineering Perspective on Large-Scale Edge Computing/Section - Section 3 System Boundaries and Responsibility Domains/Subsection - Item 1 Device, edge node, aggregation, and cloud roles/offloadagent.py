import asyncio, time, statistics, aiohttp, psutil
# Configurable weights and endpoints
EDGE_URL = "https://edge.local/api/infer"
BETA = 0.01  # energy weight (joules per ms)
SAMPLE_WINDOW = 20

# Rolling estimators
rtt_samples = []

async def estimate_network_rtt(session):
    start = time.perf_counter()
    async with session.get(EDGE_URL, timeout=1) as resp:
        await resp.read()  # minimal probe
    rtt = (time.perf_counter() - start)*1000.0
    rtt_samples.append(rtt)
    if len(rtt_samples) > SAMPLE_WINDOW:
        rtt_samples.pop(0)
    return statistics.mean(rtt_samples)

def estimate_local_time(payload_size_bytes):
    # Use cpu_percent and memory to predict local processing; placeholder model
    cpu = psutil.cpu_freq().current / psutil.cpu_freq().max
    base_ms = 50.0 * (payload_size_bytes / 100000.0)  # scale with size
    cpu_factor = max(0.5, 1.5 - cpu)
    return base_ms * cpu_factor

def estimate_energy_tx(rtt_ms, payload_bytes):
    # Simple radio power model: transmit power ~ payload size * factor
    power_per_byte = 1e-6  # J/byte heuristic
    return power_per_byte * payload_bytes + 1e-3 * (rtt_ms/1000.0)

async def decide_offload(payload_bytes):
    async with aiohttp.ClientSession() as session:
        rtt = await estimate_network_rtt(session)  # ms
    T_tx = rtt + 5.0  # add serialization overhead ms
    T_remote = 20.0  # conservative remote service time ms (measured or configured)
    T_local = estimate_local_time(payload_bytes)
    E_tx = estimate_energy_tx(rtt, payload_bytes)
    if T_local > (T_tx + T_remote + BETA * E_tx):
        return True
    return False

# Example usage in an async processing loop
async def process_loop():
    while True:
        payload = await get_next_sensor_payload()  # implemented elsewhere
        if await decide_offload(len(payload)):
            await forward_to_edge(payload)  # implement secure channel
        else:
            process_locally(payload)
        await asyncio.sleep(0.001)