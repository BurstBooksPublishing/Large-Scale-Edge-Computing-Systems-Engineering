import numpy as np
from scipy.optimize import minimize

# Networked latency and cost parameters (measure from your fleet).
L_cloud = 0.120   # seconds per request (regional GPU)
L_edge  = 0.025   # seconds per request (Jetson Xavier NX)
gamma   = 0.040   # seconds coordination penalty at mixed placement
c_cloud = 0.05    # $ per request
c_edge  = 0.005   # $ per request

# Weights: prioritize latency vs cost (tune per SLO).
w_L, w_C = 1.0, 200.0

# Optional constraints: maximum average edge energy (J/s) or availability.
edge_energy_limit = 10.0  # arbitrary units; replace with telemetry

def latency(alpha):
    return alpha*L_cloud + (1-alpha)*L_edge + gamma*alpha*(1-alpha)

def cost(alpha):
    return alpha*c_cloud + (1-alpha)*c_edge

def objective(alpha):
    a = float(alpha)
    return w_L*latency(a) + w_C*cost(a)

# Bound alpha in [0,1].
bounds = [(0.0, 1.0)]
x0 = np.array([0.5])

res = minimize(objective, x0, bounds=bounds, method='L-BFGS-B')
alpha_opt = float(res.x[0])

print(f"optimal alpha = {alpha_opt:.3f}")
print(f"expected latency = {latency(alpha_opt)*1000:.1f} ms")
print(f"expected cost = ${cost(alpha_opt):.4f} per request")
# Use result to drive placement policy in KubeEdge or OpenNESS.