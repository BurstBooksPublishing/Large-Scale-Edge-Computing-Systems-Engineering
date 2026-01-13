#!/usr/bin/env python3
"""
Compute k-shortest latency paths and filter by bandwidth and reliability.
Requires: networkx
"""
from typing import Dict, Iterable, Tuple, List
import networkx as nx
import math
import logging

logger = logging.getLogger(__name__)

def path_reliability(G: nx.DiGraph, path: Iterable[int]) -> float:
    """Return product of (1-p_e) along path."""
    r = 1.0
    for u, v in zip(path, path[1:]):
        p = G[u][v].get("p_fail", 0.0)
        r *= (1.0 - p)
    return r

def path_min_capacity(G: nx.DiGraph, path: Iterable[int]) -> float:
    """Return minimum capacity along path."""
    capacities = [G[u][v].get("capacity", 0.0) for u, v in zip(path, path[1:])]
    return min(capacities) if capacities else 0.0

def select_feasible_path(G: nx.DiGraph, s: int, t: int,
                         k: int = 10,
                         bw_req: float = 1e6,
                         rel_req: float = 0.999) -> Tuple[List[int], Dict]:
    """
    Return the best feasible path by latency among k candidates.
    Also return metrics for the selected path.
    """
    # Use latency as edge weight
    for u, v, data in G.edges(data=True):
        data.setdefault("latency", 1.0)
    try:
        candidates = nx.shortest_simple_paths(G, s, t, weight="latency")
    except nx.NetworkXNoPath:
        raise RuntimeError("No path exists")
    best = None
    best_metrics = {}
    for i, path in enumerate(candidates):
        if i >= k:
            break
        min_bw = path_min_capacity(G, path)
        rel = path_reliability(G, path)
        total_latency = sum(G[u][v].get("latency", 0.0) for u, v in zip(path, path[1:]))
        logger.debug("Candidate %d path=%s latency=%.3f bw=%.0f rel=%.6f",
                     i, path, total_latency, min_bw, rel)
        if min_bw >= bw_req and rel >= rel_req:
            # tie-breaker: prefer lower energy if provided
            energy = sum(G[u][v].get("energy_cost", 0.0) for u, v in zip(path, path[1:]))
            metrics = {"latency": total_latency, "bandwidth": min_bw, "reliability": rel, "energy": energy}
            if best is None or metrics["latency"] < best_metrics["latency"]:
                best = path
                best_metrics = metrics
    if best is None:
        raise RuntimeError("No feasible path found within k candidates")
    return best, best_metrics

# Example usage omitted for brevity; construct G with edges setting capacity, p_fail, latency.