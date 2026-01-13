from math import prod
from typing import Sequence

def conservative_reid_risk(p_leak: Sequence[float], redundancy: float = 0.0) -> float:
    """
    Compute conservative upper-bound re-identification risk.
    p_leak: per-domain leak probabilities in [0,1].
    redundancy: estimated pairwise redundancy factor in [0,1].
               0 => independent, 1 => fully redundant information.
    Returns risk in [0,1].
    """
    # clamp inputs
    p = [max(0.0, min(1.0, x)) for x in p_leak]
    if not p:
        return 0.0
    # independence-based upper bound (Eq. union bound complement)
    independent_risk = 1.0 - prod((1.0 - x) for x in p)
    # reduce risk by redundancy (conservative linear interpolation)
    risk = independent_risk * (1.0 - redundancy)
    return max(0.0, min(1.0, risk))

# Example usage on an edge orchestrator: probabilities estimated per data source
# p_leak = [0.02, 0.05, 0.01]  # toll, transit, camera
# print(conservative_reid_risk(p_leak, redundancy=0.2))