import numpy as np
import cvxpy as cp

def solve_latency_energy_cost(cycles, rtt, platform_params, alpha=1.0, beta=1.0, gamma=1.0):
    # cycles: (I,) required cycles per task in Mcycles
    # rtt: (I,J) network round-trip in seconds
    # platform_params: list of dicts with keys mu, p_idle, kappa, price, fmin, fmax
    I = cycles.shape[0]
    J = len(platform_params)
    c = cycles.reshape((I,1))  # broadcastable

    # decision vars
    x = cp.Variable((I,J), nonneg=True)        # fractional assignment
    f = cp.Variable(J)                         # frequency scaling [0,1] normalized

    # helper expressions
    mu = np.array([p['mu'] for p in platform_params])  # capacity per unit f
    p_idle = np.array([p['p_idle'] for p in platform_params])
    kappa = np.array([p['kappa'] for p in platform_params])
    price = np.array([p['price'] for p in platform_params])

    Ccap = cp.multiply(mu, f)                    # capacity vector
    u = cp.sum(cp.multiply(x, c), axis=0) / Ccap  # utilization per node

    L = cp.multiply(x, c) / f + cp.multiply(x, rtt)  # elementwise c/f + rtt
    # energy and cost
    E = p_idle + cp.multiply(kappa, cp.square(f))
    Cost = cp.multiply(price, u)

    obj = alpha * cp.sum(L) + beta * cp.sum(E) + gamma * cp.sum(Cost)

    constraints = [
        cp.sum(x, axis=1) == 1,
        u <= 1,
        f >= np.array([p['fmin'] for p in platform_params]),
        f <= np.array([p['fmax'] for p in platform_params])
    ]

    prob = cp.Problem(cp.Minimize(obj), constraints)
    prob.solve(solver=cp.ECOS, abstol=1e-6, reltol=1e-6, feastol=1e-6)

    return {'x': x.value, 'f': f.value, 'status': prob.status, 'obj': prob.value}

# Example invocation omitted for brevity; validate inputs in production.