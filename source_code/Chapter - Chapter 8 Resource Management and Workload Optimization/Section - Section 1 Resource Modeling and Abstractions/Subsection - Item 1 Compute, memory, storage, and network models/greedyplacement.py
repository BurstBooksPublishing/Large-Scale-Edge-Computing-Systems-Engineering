from dataclasses import dataclass
from typing import Dict, List, Tuple

@dataclass
class Node:
    id: str
    cpu_cycles: float    # cycles/sec available
    mem_bytes: int       # available DRAM bytes
    storage_iops: float  # sustainable IOPS
    net_bw: float        # bytes/sec available
    base_latency: float  # local baseline latency (s)

@dataclass
class Task:
    id: str
    cpu_cycles: float    # cycles required per invocation
    mem_bytes: int
    storage_iops: float
    net_bytes: float
    slo_seconds: float

def place_tasks(nodes: List[Node], tasks: List[Task],
                latency_matrix: Dict[Tuple[str,str], float]) -> Dict[str,str]:
    # Sort tasks by strictness (SLO) and demand, greedy allocate best-fit node.
    placement: Dict[str,str] = {}
    # mutable resource view
    avail: Dict[str, Node] = {n.id: Node(**n.__dict__) for n in nodes}
    tasks_sorted = sorted(tasks, key=lambda t: (t.slo_seconds, -t.cpu_cycles))
    for t in tasks_sorted:
        best_node, best_cost = None, float('inf')
        for nid, n in avail.items():
            # feasibility check
            if (n.cpu_cycles >= t.cpu_cycles and n.mem_bytes >= t.mem_bytes
                and n.storage_iops >= t.storage_iops and n.net_bw >= t.net_bytes):
                # cost = network latency + compute estimate (cycles / cycles_per_sec)
                comp_time = t.cpu_cycles / max(n.cpu_cycles*0.9, 1e-6)  # 10% headroom
                net_time = latency_matrix.get((t.id, nid), n.base_latency)
                cost = net_time + comp_time
                if cost < best_cost and cost <= t.slo_seconds:
                    best_node, best_cost = nid, cost
        if best_node is None:
            raise RuntimeError(f"No feasible node for task {t.id}")
        # allocate resources (simple subtraction)
        n = avail[best_node]
        n.cpu_cycles -= t.cpu_cycles
        n.mem_bytes -= t.mem_bytes
        n.storage_iops -= t.storage_iops
        n.net_bw -= t.net_bytes
        placement[t.id] = best_node
    return placement