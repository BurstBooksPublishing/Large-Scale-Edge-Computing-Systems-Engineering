#!/usr/bin/env python3
# TE solver: networkx topology + pulp LP -> per-commodity flows.
import networkx as nx
import pulp
from collections import defaultdict

# Build topology (replace with BGP-LS / telemetry feed in prod).
G = nx.DiGraph()
G.add_edge('A','B',capacity=100,latency=10)
G.add_edge('B','C',capacity=50,latency=20)
G.add_edge('A','C',capacity=40,latency=30)
G.add_edge('C','D',capacity=100,latency=5)

# Commodities: each item is (src, dst, demand, priority_weight)
commodities = [
    ('A','D',30,5),      # control loop, high weight
    ('A','C',20,2),      # video analytics
]

# Create LP variables f_i_j_k
prob = pulp.LpProblem("TE", pulp.LpMinimize)
f = {}
for (u,v,data) in G.edges(data=True):
    for k, (s,t,d,w) in enumerate(commodities):
        name = f"f_{u}_{v}_{k}"
        f[(u,v,k)] = pulp.LpVariable(name, lowBound=0)

# Objective: minimize latency-weighted flow (weights reflect priority)
prob += pulp.lpSum(
    data['latency'] * f[(u,v,k)] * commodities[k][3]
    for (u,v,data) in G.edges(data=True) for k in range(len(commodities))
)

# Capacity constraints
for (u,v,data) in G.edges(data=True):
    prob += pulp.lpSum(f[(u,v,k)] for k in range(len(commodities))) <= data['capacity']

# Flow conservation
for k, (s,t,d,w) in enumerate(commodities):
    for node in G.nodes():
        out = pulp.lpSum(f[(node,v,k)] for v in G.successors(node))
        inn = pulp.lpSum(f[(u,node,k)] for u in G.predecessors(node))
        rhs = d if node == s else (-d if node == t else 0)
        prob += out - inn == rhs

# Solve (use CBC or replace with commercial solver)
prob.solve(pulp.PULP_CBC_CMD(msg=False))

# Emit next-hop routing decisions (simple greedy per-commodity)
routes = defaultdict(list)
for k,(s,t,d,w) in enumerate(commodities):
    # derive per-edge positive flows
    edges = [(u,v, f[(u,v,k)].value()) for (u,v,_) in G.edges(data=True)]
    # pick edges with flow > 0 and form simple forwarding table
    for u,v,val in edges:
        if val and val > 1e-6:
            routes[k].append((u,v,val))
# Print routing hints
for k,(s,t,d,w) in enumerate(commodities):
    print(f"Commodity {k} {s}->{t} demand={d}:")
    for u,v,val in routes[k]:
        print(f"  {u} -> {v} : {val}")