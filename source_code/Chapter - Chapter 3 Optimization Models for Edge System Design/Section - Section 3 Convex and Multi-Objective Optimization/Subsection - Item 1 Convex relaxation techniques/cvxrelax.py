import numpy as np
import cvxpy as cp

# Problem data (populate from telemetry)
N, M = 200, 10
latency = np.random.rand(N, M)       # measured or predicted latencies
energy = np.random.rand(N, M)        # estimated energy costs
c = np.random.uniform(0.1, 1.0, N)   # task resource demands
C = np.full(M, 20.0)                 # node capacities
alpha, beta = 0.7, 0.3               # trade-off weights

w = alpha*latency + beta*energy      # linear objective weights
x = cp.Variable((N, M))              # relaxed variables

constraints = [
    cp.sum(x, axis=1) == 1,                       # one assignment per task
    x >= 0,
    x <= 1,
    c @ x <= C                                    # vectorized capacity: (1xN)*(NxM) <= (M,)
]

prob = cp.Problem(cp.Minimize(cp.sum(cp.multiply(w, x))), constraints)
prob.solve(solver=cp.OSQP, warm_start=True)      # efficient QP solver

X = x.value
assign = np.argmax(X, axis=1)                     # deterministic rounding

# Capacity repair: move tasks from overloaded nodes
load = np.bincount(assign, minlength=M, weights=c)
overloaded = np.where(load > C)[0]
if overloaded.size:
    # reassign tasks with smallest increase in cost until capacities met
    for j in overloaded:
        tasks_on_j = np.where(assign==j)[0]
        costs = w[tasks_on_j, :] - w[tasks_on_j, j:j+1]  # marginal costs
        # try candidate moves sorted by increasing marginal cost
        for t in tasks_on_j[np.argsort(costs.min(axis=1))]:
            new_j = np.argmin(w[t] + 1e6*(load>=C))      # prefer feasible nodes
            if load[j] - c[t] >= 0 and load[new_j] + c[t] <= C[new_j]:
                load[j] -= c[t]; load[new_j] += c[t]; assign[t] = new_j