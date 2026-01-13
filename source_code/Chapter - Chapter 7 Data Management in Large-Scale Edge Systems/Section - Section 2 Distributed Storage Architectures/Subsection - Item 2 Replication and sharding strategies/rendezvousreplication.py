from typing import List, Dict, Tuple
import hashlib, heapq

class Node:
    def __init__(self, node_id: str, weight: float = 1.0,
                 domain: str = "default", up: bool = True):
        self.id = node_id
        self.weight = max(weight, 1e-6)
        self.domain = domain
        self.up = up

def _score(node_id: str, key: str) -> int:
    # stable 160-bit hash; deterministic across processes
    h = hashlib.sha1(f"{node_id}:{key}".encode("utf-8")).digest()
    return int.from_bytes(h, "big")

def assign_replicas(shard_key: str, nodes: List[Node], R: int,
                    avoid_same_domain: bool = True) -> List[str]:
    # filter healthy nodes
    candidates = [n for n in nodes if n.up]
    if len(candidates) < R:
        raise RuntimeError("insufficient healthy nodes for replicas")

    heap: List[Tuple[float, Node]] = []
    # compute weighted score and select top R distinct-domain nodes
    for n in candidates:
        s = _score(n.id, shard_key)
        # larger weight -> prefer node; normalize to float range
        weighted = s * n.weight
        heapq.heappush(heap, (-weighted, n))  # max-heap via negative
    selected: List[Node] = []
    seen_domains = set()
    # pop until R selected, optionally skipping same-domain nodes
    while heap and len(selected) < R:
        _, n = heapq.heappop(heap)
        if avoid_same_domain and n.domain in seen_domains:
            # allow same-domain if not enough distinct domains
            if len([nd for nd in candidates if nd.domain not in seen_domains]) == 0:
                selected.append(n)
                seen_domains.add(n.domain)
            else:
                continue
        else:
            selected.append(n)
            seen_domains.add(n.domain)
    if len(selected) < R:
        raise RuntimeError("unable to satisfy placement constraints")
    return [n.id for n in selected]

# Example usage:
# nodes = [Node("edge-01", weight=2.0, domain="siteA"), ...]
# assign_replicas("shard-123", nodes, R=3)