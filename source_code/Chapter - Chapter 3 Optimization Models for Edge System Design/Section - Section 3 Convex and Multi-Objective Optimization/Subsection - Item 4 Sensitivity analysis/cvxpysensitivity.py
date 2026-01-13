import numpy as np
import cvxpy as cp

# Problem data (example): 3 tasks, 2 edge nodes with different energy rates and latencies.
energy_rate = np.array([1.0, 0.6])   # energy per unit compute on nodes
latency = np.array([[5.0, 20.0],      # latency matrix task->node (ms)
                    [10.0, 8.0],
                    [15.0, 12.0]])
compute_demand = np.array([1.0, 0.8, 1.2])  # normalized compute demand
capacity = np.array([2.0, 2.0])  # node capacities

# Decision: x[t,n] fraction of task t executed on node n (relaxed placement)
x = cp.Variable((3,2))

# Objective: total energy = sum_tn x[t,n]*demand[t]*energy_rate[n]
obj = cp.sum(cp.multiply(x, compute_demand[:,None]) * energy_rate[None,:])

# Constraints: per-task allocation sums to 1, node capacity, latency cap per task
latency_cap = 12.0  # ms, common cap for demonstration
constraints = [
    cp.sum(x, axis=1) == 1.0,
    cp.sum(cp.multiply(x, compute_demand[:,None]), axis=0) <= capacity,
    cp.multiply(x, latency) <= latency_cap  # elementwise constraint ensures per-assignment latency ok
]
prob = cp.Problem(cp.Minimize(obj), constraints)
prob.solve(solver=cp.OSQP)  # use OSQP or GUROBI in production

# Read primal and dual values
x_opt = x.value
dual_capacity = constraints[1].dual_value  # shadow prices for capacity constraints
print("Optimal allocation:\n", x_opt)
print("Duals (capacity):", dual_capacity)

# Finite-difference sensitivity for latency cap
def solve_with_cap(L):
    constraints[2] = cp.multiply(x, latency) <= L
    prob = cp.Problem(cp.Minimize(obj), constraints)
    return prob.solve(warm_start=True)

eps = 1e-3
base = prob.value
delta = solve_with_cap(latency_cap + eps) - base
approx_derivative = delta/eps
print("Finite-diff dObj/dLatencyCap ≈", approx_derivative)