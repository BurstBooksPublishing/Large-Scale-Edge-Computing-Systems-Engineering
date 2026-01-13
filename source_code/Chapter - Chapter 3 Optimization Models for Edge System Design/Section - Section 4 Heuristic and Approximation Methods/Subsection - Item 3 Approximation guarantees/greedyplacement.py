#!/usr/bin/env python3
"""Greedy submodular selection: pick k nodes to maximize coverage or latency reduction."""
from typing import Callable, List, Set, Tuple
import heapq

def greedy_select(candidates: List[str], k: int,
                  value_fn: Callable[[Set[str]], float]) -> List[str]:
    # Lazy greedy with max-heap of marginal gains for efficiency
    selected: Set[str] = set()
    # initial marginal gains
    heap: List[Tuple[float,str,Set[str]]] = []
    for v in candidates:
        gain = value_fn({v})
        heapq.heappush(heap, (-gain, v, {v}))  # use negative for max-heap

    while len(selected) < k and heap:
        neg_gain, v, _ = heapq.heappop(heap)
        # recompute marginal gain against current selection for correctness
        new_gain = value_fn(selected.union({v})) - value_fn(selected)
        if heap and -neg_gain > new_gain + 1e-12:
            # stale entry; push updated value and continue
            heapq.heappush(heap, (-new_gain, v, {v}))
            continue
        selected.add(v)
    return list(selected)

# Example value function: expected reduction in 95th-percentile latency
def example_value(selected: Set[str]) -> float:
    # Placeholder: call performance model that combines network RTT matrix,
    # node CPU capacity, and service latency model (omitted for brevity).
    # This must be deterministic and cheap to compute on edge controllers.
    return sum(hash(s) % 100 for s in selected)  # deterministic surrogate