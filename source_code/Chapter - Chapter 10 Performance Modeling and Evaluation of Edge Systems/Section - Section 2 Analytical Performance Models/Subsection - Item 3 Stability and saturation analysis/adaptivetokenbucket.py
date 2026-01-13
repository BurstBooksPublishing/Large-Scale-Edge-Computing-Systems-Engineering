#!/usr/bin/env python3
# Production-ready asyncio token-bucket with adaptive refill using CPU/GPU load.
import asyncio
import time
import psutil
from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetUtilizationRates

# Initialize NVML once (NVIDIA Jetson / discrete GPU)
nvmlInit()
_gpu = nvmlDeviceGetHandleByIndex(0)

class TokenBucket:
    def __init__(self, rate, burst):
        self.rate = rate            # tokens per second
        self.burst = burst          # max tokens
        self.tokens = burst
        self.last = time.monotonic()
        self.lock = asyncio.Lock()

    async def consume(self, n=1):
        async with self.lock:
            now = time.monotonic()
            self.tokens = min(self.burst, self.tokens + (now - self.last) * self.rate)
            self.last = now
            if self.tokens >= n:
                self.tokens -= n
                return True
            return False

    async def set_rate(self, rate):
        async with self.lock:
            self.rate = rate
            self.tokens = min(self.tokens, self.burst)

async def metrics_loop(bucket, base_rate, min_rate, max_rate, interval=1.0):
    while True:
        cpu = psutil.cpu_percent(interval=None) / 100.0
        gpu_util = nvmlDeviceGetUtilizationRates(_gpu).gpu / 100.0
        # Simple control law: reduce rate if either utilization exceeds threshold
        util = max(cpu, gpu_util)
        # Proportional scaling with margin; conservative safety margin 0.8
        target = base_rate * max(0.1, (1.0 - util) / 0.2)  # map util to rate
        target = max(min_rate, min(max_rate, target))
        await bucket.set_rate(target)
        await asyncio.sleep(interval)

async def serve_request(request_id):
    # Placeholder: call inference engine; simulate work
    await asyncio.sleep(0.01)  # simulate 10ms GPU work

async def admission_server(bucket, reader, writer):
    # Simple TCP protocol: accept a request token or send 503
    data = await reader.read(100)
    if not data:
        writer.close(); await writer.wait_closed(); return
    allowed = await bucket.consume()
    if not allowed:
        writer.write(b"HTTP/1.1 503 Service Unavailable\r\n\r\n")
        await writer.drain()
        writer.close(); await writer.wait_closed(); return
    # handle request
    await serve_request(1)
    writer.write(b"HTTP/1.1 200 OK\r\n\r\nOK")
    await writer.drain()
    writer.close(); await writer.wait_closed()

async def main():
    base_rate = 80.0            # target tokens/sec under nominal load
    min_rate = 5.0
    max_rate = 120.0
    bucket = TokenBucket(rate=base_rate, burst=200)
    # Start metrics controller
    asyncio.create_task(metrics_loop(bucket, base_rate, min_rate, max_rate))
    server = await asyncio.start_server(lambda r,w: admission_server(bucket,r,w),
                                        '0.0.0.0', 8080)
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.run(main())