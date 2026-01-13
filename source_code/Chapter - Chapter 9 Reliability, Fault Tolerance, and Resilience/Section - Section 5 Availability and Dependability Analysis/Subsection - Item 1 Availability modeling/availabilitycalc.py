#!/usr/bin/env python3
"""
Availability utilities for edge clusters.
Assumes independent nodes unless common_cause_prob provided.
"""
from math import comb
from typing import Optional

def ctmc_availability(mtbf_hours: float, mttr_hours: float) -> float:
    # MTBF and MTTR must be positive
    if mtbf_hours <= 0 or mttr_hours <= 0:
        raise ValueError("MTBF and MTTR must be positive")
    return mtbf_hours / (mtbf_hours + mttr_hours)

def k_of_n_availability(a: float, n: int, k: int, common_cause_prob: Optional[float]=None) -> float:
    # a: per-node availability in [0,1]; n,k integers
    if not (0.0 <= a <= 1.0):
        raise ValueError("Availability must be in [0,1]")
    if not (1 <= k <= n):
        raise ValueError("Require 1 <= k <= n")
    sys_avail = sum(comb(n, i) * (a**i) * ((1.0-a)**(n-i)) for i in range(k, n+1))
    # Adjust for simple common-cause failure model: with probability p_c all fail.
    if common_cause_prob:
        p_c = float(common_cause_prob)
        if not (0.0 <= p_c <= 1.0):
            raise ValueError("common_cause_prob must be in [0,1]")
        # If common cause occurs, availability becomes 0 for this simple model.
        sys_avail = (1.0 - p_c) * sys_avail
    return sys_avail

# Example usage (to be invoked from tests or orchestration scripts):
if __name__ == "__main__":
    node_a = ctmc_availability(mtbf_hours=8760.0, mttr_hours=2.0)  # 1-year MTBF, 2h repair
    print(f"Per-node availability: {node_a:.6f}")
    print("2-of-3 availability (p_c=0.001):",
          k_of_n_availability(node_a, n=3, k=2, common_cause_prob=0.001))