#!/usr/bin/env python3
# Compute nondominated cost-performance frontier for node mixes.
from itertools import product
import math
import numpy as np

# Node catalogue: (name, cap_fps, capex_usd, opex_usd_per_day, mtbf_hours)
NODES = [
    ("jetson_xavier_nx", 30, 800.0, 1.5, 20000.0),
    ("raspberry_pi_4", 6, 75.0, 0.3, 10000.0),
    ("cloud_c5_large", 200, 0.10, 2.5, 1e6)  # cloud paid per-use (capex ~0)
]

Lambda = 600.0                     # total arrival frames/s
T_max = 0.05                       # seconds
R_min = 0.999                     # availability target over deployment window
deployment_days = 365

def availability(mtbf_hours, count):
    # Exponential failure model, independent nodes; availability over deployment window
    lam = 1.0 / mtbf_hours
    t_hours = deployment_days * 24.0
    # node survival prob
    p_up = math.exp(-lam * t_hours)
    # system up if at least one node of that type exists and not all fail.
    if count == 0:
        return 0.0
    return 1.0 - (1.0 - p_up)**count

def evaluate_mix(counts):
    # counts: tuple of ints matching NODES order
    total_nodes = sum(counts)
    if total_nodes == 0:
        return None
    # effective per-node arrival assumed split evenly across all nodes
    lambda_per_node = Lambda / total_nodes
    # check M/M/1 latency constraint for each node type present
    for (name, mu, capex, opex_day, mtbf), n in zip(NODES, counts):
        if n == 0:
            continue
        if lambda_per_node >= mu:
            return None
        mean_latency = 1.0 / (mu - lambda_per_node)
        if mean_latency > T_max:
            return None
    # cost: CAPEX + OPEX over deployment window (approx)
    capex = sum(n * capex for (_, _, capex, _, _), n in zip(NODES, counts))
    opex = sum(n * opex_day for (_, _, _, opex_day, _), n in zip(NODES, counts)) * deployment_days
    cost = capex + opex
    # availability combined across heterogeneous types (approx as at-least-one up)
    avail = 1.0
    # compute probability system is down: all nodes of every type are down
    prob_all_down = 1.0
    for (name, mu, capex, opex_day, mtbf), n in zip(NODES, counts):
        prob_all_down *= (1.0 - availability(mtbf, n))
    avail = 1.0 - prob_all_down
    return {"counts": counts, "cost": cost, "availability": avail}

# search reasonable ranges
max_counts = [100, 200, 10]
results = []
for counts in product(*(range(0, m+1) for m in max_counts)):
    res = evaluate_mix(counts)
    if res and res["availability"] >= R_min:
        results.append(res)

# extract nondominated (Pareto) frontier by cost vs total_nodes
results.sort(key=lambda r: (r["cost"], sum(r["counts"])))
pareto = []
best_cost = float("inf")
for r in results:
    if r["cost"] < best_cost:
        pareto.append(r)
        best_cost = r["cost"]

for p in pareto:
    print(f"mix={p['counts']}, cost=${p['cost']:.0f}, availability={p['availability']:.6f}")