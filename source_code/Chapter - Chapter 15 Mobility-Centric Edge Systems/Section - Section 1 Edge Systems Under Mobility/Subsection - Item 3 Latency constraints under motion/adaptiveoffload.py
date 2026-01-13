import asyncio, math, statistics
# Minimal, production-ready decision loop. Replace probes with platform APIs.
async def probe_rtt(host="edge.local"):
    # ICMP or application-layer RTT probe to current edge node.
    proc = await asyncio.create_subprocess_exec("ping","-c","3","-W","1",host,
        stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL)
    out,_ = await proc.communicate()
    times = [float(t.split(b"=")[-1]) for t in out.split() if b"time=" in t]
    return statistics.mean(times) if times else 0.1

async def probe_bw():
    # Quick bandwidth probe using TCP handshake + small transfer; use iperf3 in real deployments.
    return 20e6  # 20 Mbps baseline; replace with measured value.

def handover_prob_estimate(speed_m_s, cell_radius_m, interval_s):
    # Poisson approx: expected handovers per interval.
    lam = speed_m_s*interval_s / max(cell_radius_m,1.0)
    return 1 - math.exp(-lam)  # probability >=1 handover.

async def decide_offload(latency_budget_ms=20, speed=30.0, interval=0.1):
    rtt = await probe_rtt()
    bw = await probe_bw()
    p_ho = handover_prob_estimate(speed, 300.0, interval)
    # Estimate migration penalty conservatively.
    T_mig_ms = 50.0 if p_ho>0.05 else 10.0
    sigma_rtt = max(1.0, 0.2*rtt)  # empirical model
    # Compute 99.9% tail term.
    tail_ms = sigma_rtt * 3.09
    expected_ms = rtt*2 + 5.0 + T_mig_ms*p_ho + tail_ms  # uplink+downlink approx + proc(5ms)
    return expected_ms <= latency_budget_ms, dict(expected_ms=expected_ms, rtt=rtt, p_ho=p_ho, bw=bw)

# Example usage in async main loop.
async def main_loop():
    while True:
        offload_ok, stats = await decide_offload()
        if offload_ok:
            # route work to MEC via Kubernetes k3s service or direct gRPC.
            pass
        else:
            # run local fallback on-device (TensorRT, ROS2 node, or RTOS task).
            pass
        await asyncio.sleep(0.05)  # control cadence

if __name__ == "__main__":
    asyncio.run(main_loop())