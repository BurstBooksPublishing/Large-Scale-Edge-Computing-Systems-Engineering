from typing import List, Dict, Tuple
import math
import logging

# Candidate node metrics: latency_ms, cpu_util (0..1), energy_w
Node = Dict[str, float]

def score_node(node: Node, weights: Tuple[float,float,float]=(0.5,0.3,0.2)) -> float:
    """
    Score a node where higher is better.
    weights: (latency_weight, cpu_headroom_weight, energy_weight).
    """
    latency = node["latency_ms"]
    cpu_headroom = max(0.0, 1.0 - node["cpu_util"])
    energy = node["energy_w"]

    # Normalize metrics to [0,1] using operational bounds
    lat_norm = math.exp(-latency / 50.0)        # favors <50ms
    cpu_norm = cpu_headroom                     # already 0..1
    energy_norm = 1.0 / (1.0 + (energy / 20.0)) # favors low-energy nodes

    w_lat, w_cpu, w_en = weights
    return w_lat * lat_norm + w_cpu * cpu_norm + w_en * energy_norm

def rank_candidates(candidates: List[Node]) -> List[Tuple[Node,float]]:
    """Return candidates sorted by descending score."""
    scored = [(c, score_node(c)) for c in candidates]
    scored.sort(key=lambda x: (x[1], -x[0]["latency_ms"]), reverse=True)
    logging.info("Ranked %d candidates", len(candidates))
    return scored

# Example usage (called by orchestrator): provide live metrics from node agent.