from typing import NamedTuple
import math

class Estimate(NamedTuple):
    L_commit: float   # seconds
    net_ceiling: float  # tx/sec
    cpu_ceiling: float  # tx/sec
    latency_ceiling: float  # tx/sec
    Tmax: float
    bottleneck: str

def estimate(B: float, S: float, C: float, sigma: float,
             R: int, RTT: float, t_proc: float, t_io: float) -> Estimate:
    """
    B: bandwidth bytes/sec
    S: bytes per tx (total consensus traffic)
    C: crypto ops/sec available (verifies/sec)
    sigma: crypto ops per tx
    R: network rounds
    RTT: mean RTT seconds
    t_proc: processing time seconds
    t_io: durable write time seconds
    """
    L_commit = R * RTT + t_proc + t_io
    net_ceiling = B / S if S > 0 else float('inf')
    cpu_ceiling = C / sigma if sigma > 0 else float('inf')
    latency_ceiling = 1.0 / L_commit if L_commit > 0 else float('inf')
    Tmax = min(net_ceiling, cpu_ceiling, latency_ceiling)
    # Determine dominant bottleneck
    ceilings = {'network': net_ceiling, 'cpu': cpu_ceiling, 'latency': latency_ceiling}
    bottleneck = min(ceilings, key=ceilings.get)
    return Estimate(L_commit, net_ceiling, cpu_ceiling, latency_ceiling, Tmax, bottleneck)

# Example call: 10 Mbps, 5 kB per tx, 2000 verifies/sec, 1 verify/tx,
# 3 rounds, 50 ms RTT, 10 ms proc, 5 ms io
if __name__ == "__main__":
    est = estimate(B=10e6/8, S=5_000, C=2000, sigma=1, R=3,
                   RTT=0.05, t_proc=0.01, t_io=0.005)
    print(est)