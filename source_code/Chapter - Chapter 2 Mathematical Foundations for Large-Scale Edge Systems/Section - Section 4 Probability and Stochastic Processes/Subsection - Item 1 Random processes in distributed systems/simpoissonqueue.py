#!/usr/bin/env python3
"""Simulate many Poisson sources feeding a single edge server.
Outputs mean and tail latency percentiles."""
import heapq, math
import numpy as np
from typing import List, Tuple

Event = Tuple[float, str, dict]  # (time, type, payload)

def exp(rng, rate):
    return rng.exponential(1.0 / rate)

def run_sim(n_devices: int, device_rate: float, service_rate: float,
            sim_time: float, rng_seed: int = 42):
    rng = np.random.default_rng(rng_seed)
    heap: List[Event] = []
    # schedule initial arrivals per device
    for dev in range(n_devices):
        t = exp(rng, device_rate)
        heapq.heappush(heap, (t, 'arrival', {'device': dev}))
    server_busy_until = 0.0
    queue: List[float] = []  # arrival times waiting
    latencies: List[float] = []
    while heap:
        t, etype, payload = heapq.heappop(heap)
        if t > sim_time:
            break
        if etype == 'arrival':
            # schedule next arrival for same device
            next_t = t + exp(rng, device_rate)
            heapq.heappush(heap, (next_t, 'arrival', payload))
            # model network jitter as lognormal
            net_delay = rng.lognormal(mean=math.log(0.01), sigma=0.5)
            arrival_at_server = t + net_delay
            heapq.heappush(heap, (arrival_at_server, 'to_server', {'orig': t}))
        elif etype == 'to_server':
            if t >= server_busy_until:
                # server idle, start service immediately
                service_time = exp(rng, service_rate)
                server_busy_until = t + service_time
                latency = server_busy_until - payload['orig']
                latencies.append(latency)
                heapq.heappush(heap, (server_busy_until, 'service_complete', {}))
            else:
                # enqueue arrival timestamp
                queue.append(payload['orig'])
        elif etype == 'service_complete':
            if queue:
                orig = queue.pop(0)
                # start next service immediately
                service_time = exp(rng, service_rate)
                server_busy_until = t + service_time
                latency = server_busy_until - orig
                latencies.append(latency)
                heapq.heappush(heap, (server_busy_until, 'service_complete', {}))
            else:
                server_busy_until = t
    if not latencies:
        return {}
    arr = np.array(latencies)
    return {
        'mean_s': float(arr.mean()),
        'p50_s': float(np.percentile(arr, 50)),
        'p95_s': float(np.percentile(arr, 95)),
        'p99_s': float(np.percentile(arr, 99)),
        'samples': len(arr)
    }

if __name__ == '__main__':
    stats = run_sim(n_devices=1000, device_rate=0.0205,
                    service_rate=30.0, sim_time=1000.0)
    print(stats)  # integrate into CI or dashboards