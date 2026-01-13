from ortools.sat.python import cp_model

# Problem data (replace with telemetry from monitoring)
tasks = [
  {'id':'cam1','r':2,'s':1.0,'D':0.08}, # r: CPU units, s: cycles normalized
  {'id':'cam2','r':2,'s':1.0,'D':0.08},
  {'id':'analytics','r':4,'s':5.0,'D':1.0},
]
nodes = [
  {'id':'xavier1','C':8,'c':4.0,'RTT_base':0.005,'W':0.005}, # local edge
  {'id':'cloud','C':32,'c':10.0,'RTT_base':0.05,'W':0.02},  # regional cloud
]

# Precompute L_ij = RTT + S_i(c_j) + W_j
L = {}
for i, t in enumerate(tasks):
  for j, n in enumerate(nodes):
    S = t['s'] / n['c']                 # deterministic service time
    L[(i,j)] = n['RTT_base'] + S + n['W']

model = cp_model.CpModel()
x = {}
for i in range(len(tasks)):
  for j in range(len(nodes)):
    x[(i,j)] = model.NewBoolVar(f"x_{i}_{j}")

# Each task assigned to exactly one node
for i in range(len(tasks)):
  model.Add(sum(x[(i,j)] for j in range(len(nodes))) == 1)

# Node capacity constraints
for j in range(len(nodes)):
  model.Add(sum(tasks[i]['r'] * x[(i,j)] for i in range(len(tasks))) <= nodes[j]['C'])

# Deadlines and minimax objective variable T (milliseconds)
T = model.NewIntVar(0, 10000, "T_ms")
for i in range(len(tasks)):
  # scale latencies to integer ms
  lat_expr = sum(int(1000 * L[(i,j)]) * x[(i,j)] for j in range(len(nodes)))
  model.Add(lat_expr <= int(1000 * tasks[i]['D']))
  model.Add(T >= lat_expr)

model.Minimize(T)
solver = cp_model.CpSolver()
solver.parameters.max_time_in_seconds = 10
res = solver.Solve(model)

# Emit assignments for a scheduler extender
for i, t in enumerate(tasks):
  for j, n in enumerate(nodes):
    if solver.Value(x[(i,j)]):
      print(f"assign {t['id']} -> {n['id']}  # expected latency {L[(i,j)]:.3f}s")