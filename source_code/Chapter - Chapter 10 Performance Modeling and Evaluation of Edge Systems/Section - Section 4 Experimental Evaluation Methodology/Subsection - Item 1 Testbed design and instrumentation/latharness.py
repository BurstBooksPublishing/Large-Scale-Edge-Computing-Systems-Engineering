import time, asyncio, csv
from prometheus_client import Gauge, push_to_gateway
import grpc  # app-specific RPC client

LATENCY_GAUGE = Gauge('edge_rpc_latency_ms','RPC latency in ms', ['node','rpc'])
PUSHGW = 'http://promgateway.example:9091'

async def measure_once(stub, rpc_name, node_id):
    # Use CLOCK_MONOTONIC_RAW for monotonic interval measurements
    t0 = time.clock_gettime(time.CLOCK_MONOTONIC_RAW)
    resp = await stub.CallAsync()            # await async RPC; use proper gRPC asyncio client
    t1 = time.clock_gettime(time.CLOCK_MONOTONIC_RAW)
    # If NIC hardware timestamps available, replace t0/t1 with PHC-derived times here
    latency_ms = (t1 - t0) * 1000.0
    LATENCY_GAUGE.labels(node=node_id, rpc=rpc_name).set(latency_ms)
    push_to_gateway(PUSHGW, job='lat_harness', grouping_key={'node':node_id})
    return latency_ms

async def run_bench(stub, rpc_name, node_id, n, out_csv):
    # Pilot run to estimate sigma
    samples = []
    for _ in range(n):
        samples.append(await measure_once(stub, rpc_name, node_id))
        await asyncio.sleep(0.01)              # pacing to control queueing
    with open(out_csv,'w',newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp_ms','latency_ms'])
        ts = int(time.time()*1000)
        for s in samples:
            writer.writerow([ts, s])
# Entry point expects an asyncio event loop and a configured gRPC stub.