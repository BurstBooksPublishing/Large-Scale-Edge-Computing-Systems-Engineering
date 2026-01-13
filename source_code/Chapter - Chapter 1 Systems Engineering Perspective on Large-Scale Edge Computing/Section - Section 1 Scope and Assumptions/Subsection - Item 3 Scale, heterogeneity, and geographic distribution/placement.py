from dataclasses import dataclass
from typing import List, Dict, Optional
import math

SPEED_KM_PER_MS = 200.0  # approx 200,000 km/s -> 200 km/ms for fiber

@dataclass
class Node:
    id: str
    compute_cycles_per_ms: float  # cycles/ms
    bandwidth_mbps: float         # Mbps
    distance_km: float            # distance to client in km

@dataclass
class Task:
    id: str
    required_cycles: float        # cycles per inference/request
    payload_kb: float             # bytes to send (kB)
    max_latency_ms: float

def propagation_ms(d_km: float) -> float:
    return d_km / SPEED_KM_PER_MS

def tx_ms(size_kb: float, bw_mbps: float) -> float:
    if bw_mbps <= 0:
        return float('inf')
    # convert kB to Mb: 1 kB = 8e-3 Mb
    size_mb = size_kb * 8e-3
    return (size_mb / bw_mbps) * 1000.0  # ms

def processing_ms(required_cycles: float, cycles_per_ms: float) -> float:
    if cycles_per_ms <= 0:
        return float('inf')
    return required_cycles / cycles_per_ms

def place_tasks(nodes: List[Node], tasks: List[Task]) -> Dict[str, Optional[str]]:
    assignments: Dict[str, Optional[str]] = {}
    # simple per-node remaining cycles budget (for this scheduling epoch)
    remaining_cycles = {n.id: n.compute_cycles_per_ms * 1000.0 for n in nodes}  # support 1s window
    for t in tasks:
        # sort nodes by estimated RTT (2*propagation + tx) to prefer locality
        candidates = sorted(nodes, key=lambda n: 2*propagation_ms(n.distance_km) + tx_ms(t.payload_kb, n.bandwidth_mbps))
        assigned = None
        for n in candidates:
            est_latency = propagation_ms(n.distance_km) + tx_ms(t.payload_kb, n.bandwidth_mbps) + processing_ms(t.required_cycles, n.compute_cycles_per_ms)
            if est_latency <= t.max_latency_ms and remaining_cycles[n.id] >= t.required_cycles:
                remaining_cycles[n.id] -= t.required_cycles
                assigned = n.id
                break
        assignments[t.id] = assigned
    return assignments

# Example usage (production systems would fetch these from telemetry APIs)
_nodes = [Node("jetson-1", 5e6, 100.0, 0.5), Node("regional-1", 1e7, 1000.0, 50.0)]
_tasks = [Task("vision-1", 2e7, 200.0, 20.0), Task("telemetry-1", 5e5, 10.0, 200.0)]
# assign = place_tasks(_nodes, _tasks)