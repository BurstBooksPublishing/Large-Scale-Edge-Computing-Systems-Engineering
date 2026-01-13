import hashlib
import math
from typing import Dict, Iterable, Tuple

def gini(loads: Iterable[float]) -> float:
    L = sorted(float(x) for x in loads)
    n = len(L)
    if n == 0: return 0.0
    mean = sum(L) / n
    if mean == 0: return 0.0
    num = sum(abs(L[i] - L[j]) for i in range(n) for j in range(n))
    return num / (2 * n * n * mean)

def imbalance_factor(loads: Iterable[float]) -> float:
    L = list(loads)
    n = len(L)
    if n == 0: return 1.0
    mean = sum(L)/n
    return max(L)/mean if mean > 0 else float('inf')

def _hash(key: bytes) -> int:
    return int(hashlib.sha256(key).hexdigest(), 16)

def weighted_rendezvous_assign(key: str, nodes: Dict[str, float]) -> str:
    # nodes: mapping node_id -> weight (capacity)
    best = None
    best_score = -math.inf
    kh = key.encode('utf-8')
    for nid, weight in nodes.items():
        # combine key with node id deterministically
        h = _hash(kh + nid.encode('utf-8'))
        score = math.log(weight + 1e-12) - math.log(h + 1)  # high score favored
        if score > best_score:
            best_score = score
            best = nid
    return best

# Example usage (to be called from orchestration code)
if __name__ == "__main__":
    loads = [100, 10, 5, 2]  # measured events/sec per shard
    print("Gini:", gini(loads))
    print("Imbalance factor:", imbalance_factor(loads))

    nodes = {"edge1": 1.0, "edge2": 4.0, "edge3": 8.0}  # weights reflect capacity
    key = "sensor-abc-123"
    assigned = weighted_rendezvous_assign(key, nodes)
    print("Assigned node:", assigned)