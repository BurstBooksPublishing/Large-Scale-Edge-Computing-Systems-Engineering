#!/usr/bin/env python3
"""
Compute stale probability and expected quorum latency.
Assumes combinatorial uniform selection of R replicas for reads.
Designed for inclusion in deployment tooling.
"""
from math import comb
from typing import List, Tuple

def stale_probability(N: int, R: int, W: int) -> float:
    # If R or W invalid, raise ValueError to fail fast in pipelines.
    if not (1 <= R <= N and 1 <= W <= N):
        raise ValueError("R and W must be in [1, N]")
    if N - W < R:
        return 0.0  # impossible to pick R entirely from non-updated set
    return comb(N - W, R) / comb(N, R)

def expected_quorum_latency(rtt_ms: List[float], R: int) -> float:
    # Estimate expected latency by picking the R fastest replicas (read-locality).
    # For worst-case site-selection, use max of R slowest; here we support both modes.
    if R > len(rtt_ms):
        raise ValueError("R larger than replica count")
    sorted_rtts = sorted(rtt_ms)
    # Assume client selects nearest R replicas for reads (typical in edge).
    return max(sorted_rtts[:R])  # ms

# Example usage for an industrial edge scenario:
if __name__ == "__main__":
    # Replicas located in: factory (2 ms), regional edge (20 ms), cloud (80 ms)
    rtt_samples = [2.0, 2.5, 20.0, 22.0, 80.0]  # ms
    N = len(rtt_samples)
    candidates = [(1,3), (2,2), (3,3)]  # (R,W) pairs
    for R,W in candidates:
        p = stale_probability(N, R, W)
        L = expected_quorum_latency(rtt_samples, R)
        print(f"(R={R},W={W}): stale={p:.4f}, expected_read_latency={L:.1f} ms")