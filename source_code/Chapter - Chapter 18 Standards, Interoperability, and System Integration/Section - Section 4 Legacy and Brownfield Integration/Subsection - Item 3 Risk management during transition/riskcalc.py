#!/usr/bin/env python3
# Compute expected downtime and suggest canary stages.
import math
from typing import List

def expected_downtime(failure_prob: float, per_failure_downtime_hr: float, n_nodes: int) -> float:
    # independent nodes approximation
    return n_nodes * failure_prob * per_failure_downtime_hr

def suggest_stages(total_nodes: int, failure_prob: float, per_failure_downtime_hr: float, allow_hr: float) -> List[int]:
    # return list of cumulative nodes per stage keeping expected downtime <= allow_hr
    stages = []
    cum = 0
    for stage_size in [1,2,5,10,20,50,100]:
        if cum >= total_nodes: break
        add = min(stage_size, total_nodes - cum)
        cum += add
        if expected_downtime(failure_prob, per_failure_downtime_hr, cum) <= allow_hr:
            stages.append(cum)
        else:
            # reduce stage size until within bounds
            while add>0 and expected_downtime(failure_prob, per_failure_downtime_hr, cum) > allow_hr:
                add -= 1
                cum -= 1
            if add>0: stages.append(cum)
            break
    return stages

if __name__ == "__main__":
    total = 200          # nodes to migrate
    p_fail = 0.01        # per-node yearly failure probability during transition
    down_hr = 1.0        # downtime in hours per failure
    allow = (1 - 0.9995)*8760  # example allowable downtime for 99.95% target
    print("Allowable downtime (hr/year):", allow)
    print("Suggested cumulative stages:", suggest_stages(total, p_fail, down_hr, allow))