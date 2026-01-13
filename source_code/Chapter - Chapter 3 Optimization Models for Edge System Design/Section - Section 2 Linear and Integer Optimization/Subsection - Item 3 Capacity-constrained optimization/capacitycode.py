import pulp
# Node and task definitions (example values)
nodes = {
    "agg1": {"cpu": 64.0, "mem": 256.0, "cost": 1.0},
    "edgeA": {"cpu": 16.0, "mem": 64.0,  "cost": 0.7},
    "pi01":  {"cpu": 4.0,  "mem": 4.0,   "cost": 0.2},
}
tasks = {
    "cam01": {"cpu": 8.0, "mem": 6.0, "slo_ms": 50},
    "cam02": {"cpu": 2.0, "mem": 2.0, "slo_ms": 100},
    "ml01":  {"cpu": 20.0,"mem": 32.0,"slo_ms": 80},
}
# Latency matrix (ms)
latency = {
    ("cam01","agg1"): 40, ("cam01","edgeA"): 20, ("cam01","pi01"): 10,
    ("cam02","agg1"): 90, ("cam02","edgeA"): 70, ("cam02","pi01"): 150,
    ("ml01","agg1"): 60,  ("ml01","edgeA"): 40,  ("ml01","pi01"): 200,
}
# Build ILP
prob = pulp.LpProblem("capacitated_placement", pulp.LpMinimize)
x = pulp.LpVariable.dicts("x", (tasks.keys(), nodes.keys()),
                          lowBound=0, upBound=1, cat="Binary")
# Objective: minimize sum(cost * indicator)
prob += pulp.lpSum(nodes[j]["cost"] * x[i][j] for i in tasks for j in nodes)
# Assignment constraints and latency prefilter (disallow infeasible assignments)
for i in tasks:
    prob += pulp.lpSum(x[i][j] for j in nodes if latency.get((i,j), 1e9) <= tasks[i]["slo_ms"]) == 1
    for j in nodes:
        if latency.get((i,j), 1e9) > tasks[i]["slo_ms"]:
            prob += x[i][j] == 0
# Capacity constraints (CPU and memory)
for j in nodes:
    prob += pulp.lpSum(tasks[i]["cpu"] * x[i][j] for i in tasks) <= nodes[j]["cpu"]
    prob += pulp.lpSum(tasks[i]["mem"] * x[i][j] for i in tasks) <= nodes[j]["mem"]
# Solve with CBC
prob.solve(pulp.PULP_CBC_CMD(msg=False))
# Output
for i in tasks:
    for j in nodes:
        if pulp.value(x[i][j]) > 0.5:
            print(f"Task {i} -> Node {j}")