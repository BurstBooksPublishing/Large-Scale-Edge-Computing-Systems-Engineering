from dataclasses import dataclass
from typing import List, Optional

@dataclass
class EdgeNode:
    id: str
    cpu_cores: int
    mem_mb: int
    uplink_bw_mbps: float  # available uplink bandwidth
    assigned_devices: int = 0

@dataclass
class Device:
    id: str
    cpu_req: float  # cores
    mem_req_mb: int
    samp_rate: float  # samples/s
    samp_size_kb: float

def assign_devices(devices: List[Device], edges: List[EdgeNode],
                   max_devices_per_edge: int, agg_factor: float = 0.2) -> Optional[List[EdgeNode]]:
    # greedy assignment verifying capacity and uplink constraints
    for d in devices:
        placed = False
        for e in sorted(edges, key=lambda x: x.assigned_devices):
            # check per-device resource fit
            if e.assigned_devices >= max_devices_per_edge:
                continue
            # check uplink bandwidth headroom using eq. \eqref{eq:bandwidth}
            added_bw_mbps = (d.samp_rate * d.samp_size_kb * agg_factor) / 125.0  # kB->Mb
            if e.uplink_bw_mbps - (e.assigned_devices * added_bw_mbps) <= 0:
                continue
            # check CPU/memory heuristic (simple fractional check)
            if (e.cpu_cores * 1000) < ( (e.assigned_devices+1) * d.cpu_req * 1000):
                continue
            if e.mem_mb < (e.assigned_devices+1) * d.mem_req_mb:
                continue
            # assign device
            e.assigned_devices += 1
            placed = True
            break
        if not placed:
            return None  # capacity failure; higher-level rebalancing needed
    return edges  # successful assignment
# Production systems should replace greedy logic with global optimizer (ILP/LP) for efficiency.