#!/usr/bin/env python3
"""
energy_offload.py - decide per-task offload based on energy and latency.
Integrate with ROS2 or MAVLink by calling decide_offload() with measured params.
"""
from typing import NamedTuple
import logging
import time
import math

logger = logging.getLogger("energy_offload")
logging.basicConfig(level=logging.INFO)

class Params(NamedTuple):
    cpu_power_w: float       # average CPU active power (W)
    cpu_time_s: float        # local compute time (s)
    tx_power_w: float        # modem transmit power (W)
    payload_bytes: int       # bytes to transmit if offloading
    link_rate_bps: float     # current uplink rate (bps)
    net_rtt_s: float         # network round-trip baseline (s)
    remote_proc_s: float     # expected remote processing time (s)
    latency_deadline_s: float# task deadline (s)

def compute_local_energy(p: Params) -> float:
    # energy for local compute
    return p.cpu_power_w * p.cpu_time_s

def compute_offload_energy(p: Params) -> float:
    # conservative tx time estimate with a small protocol overhead
    overhead = 1.1
    tx_time = overhead * (p.payload_bytes * 8) / max(p.link_rate_bps, 1.0)
    return p.tx_power_w * tx_time

def compute_local_latency(p: Params) -> float:
    return p.cpu_time_s

def compute_offload_latency(p: Params) -> float:
    # uplink + network RTT (half RTT) + remote processing + downlink (assumed symmetric small)
    tx_time = (p.payload_bytes * 8) / max(p.link_rate_bps, 1.0)
    return tx_time + p.net_rtt_s/2.0 + p.remote_proc_s

def decide_offload(p: Params) -> dict:
    """Return decision dict: {'offload':bool,'reason':str,'metrics':{...}}"""
    el = compute_local_energy(p)
    eo = compute_offload_energy(p)
    ll = compute_local_latency(p)
    lo = compute_offload_latency(p)

    logger.debug("E_local=%.3f J, E_off=%.3f J, L_loc=%.3f s, L_off=%.3f s", el, eo, ll, lo)

    # must meet deadline
    if ll <= p.latency_deadline_s and lo <= p.latency_deadline_s:
        # both feasible, choose lower energy
        offload = eo < el
        reason = "both feasible; energy-optimal"
    elif ll <= p.latency_deadline_s:
        offload = False
        reason = "only local meets deadline"
    elif lo <= p.latency_deadline_s:
        offload = True
        reason = "only offload meets deadline"
    else:
        offload = False
        reason = "deadline cannot be met; prefer local for robustness"

    return {
        "offload": offload,
        "reason": reason,
        "metrics": {"E_local_J": el, "E_offload_J": eo, "L_local_s": ll, "L_offload_s": lo}
    }

# Example runtime usage when integrated into companion loop
if __name__ == "__main__":
    params = Params(cpu_power_w=15.0, cpu_time_s=0.8, tx_power_w=2.0,
                    payload_bytes=500_000, link_rate_bps=5e6,
                    net_rtt_s=0.3, remote_proc_s=0.05, latency_deadline_s=1.0)
    decision = decide_offload(params)
    logger.info("Decision: %s, reason: %s, metrics: %s", decision["offload"], decision["reason"], decision["metrics"])