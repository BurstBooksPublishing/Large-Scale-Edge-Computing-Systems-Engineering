import cvxpy as cp
import numpy as np

# Problem data (replace with telemetry/configuration)
N = 3  # nodes: Jetson, Pi4, Cloud
K = 4  # workloads
ell = np.random.uniform(1,10,(N,K))   # per-node latency estimates (ms)
r = np.random.uniform(0.1,1.0,K)      # workload CPU demand (cores)
cap = np.array([8.0,4.0,32.0])        # node capacities (cores)
P_idle = np.array([10.0,3.5,50.0])    # Watts
P_max = np.array([30.0,10.0,200.0])   # Watts
c = np.array([0.05,0.02,0.005])       # $/core-second

# Variables: assign fractions
x = cp.Variable((N,K), nonneg=True)

# Utilization per node (linearized)
u = (x @ r) / cap  # elementwise broadcast in CVXPY; ensure shapes align

# Convex expressions
L = cp.sum(cp.multiply(x, ell))                       # total latency proxy
E = cp.sum(P_idle + (P_max - P_idle)*cp.reshape(u, (N,1)) )  # approximate energy term
C = cp.sum(cp.multiply(c, u))                         # cost

# Feasible set: per-workload conservation and capacity
constraints = [cp.sum(x, axis=0) == 1.0]              # each workload fully assigned
constraints += [x @ r <= cap]                         # capacity constraints

# Sweep weights to obtain Pareto points
pareto = []
weights = np.linspace(0.1,0.9,9)
for w in weights:
    obj = cp.Minimize(w*L + (1-w)*E + 0.01*C)         # small cost weight for tie-breaking
    prob = cp.Problem(obj, constraints)
    prob.solve(solver=cp.ECOS, abstol=1e-6)           # solver selection for embedded edges
    pareto.append((w, prob.value, x.value))
# persisting pareto[] yields frontier for operator analysis