from typing import Sequence

def worst_case_delay(burst_bits: float, rate_bps: float,
                     service_rates_bps: Sequence[float],
                     service_latencies_s: Sequence[float]) -> float:
    """
    Compute worst-case delay (seconds) for arrival alpha(t)=burst + rate*t
    crossing cascaded rate-latency servers.
    Units: bits, bits/s, seconds.
    Raises ValueError if service capacity is insufficient.
    """
    if len(service_rates_bps) != len(service_latencies_s):
        raise ValueError("service_rates and service_latencies must match lengths")
    R_min = min(service_rates_bps)
    T_sum = sum(service_latencies_s)
    spare = R_min - rate_bps
    if spare <= 0:
        raise ValueError("Insufficient service rate: R_min <= arrival rate")
    queue_delay = burst_bits / spare
    return T_sum + queue_delay

# Example usage (industrial sensor):
# burst=10_000 bits, rate=50_000 bps, R1=1e6, T1=0.002, R2=5e5, T2=0.005
# expected ~0.0292 s