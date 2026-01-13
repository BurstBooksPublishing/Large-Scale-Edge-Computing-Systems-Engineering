from pulp import LpProblem, LpMinimize, LpVariable, lpSum, LpBinary, PULP_CBC_CMD
import numpy as np

def place_regional_aggregators(dist_matrix, weights, capacities, costs):
    """
    dist_matrix: (N_sites, M_candidates) RTT or cost matrix (numpy array)
    weights: (N_sites,) request rates or traffic weights
    capacities: (M_candidates,) capacity per candidate (same units as weights sum)
    costs: (M_candidates,) fixed cost to open candidate
    Returns: (selected_regions, assignment_vector)
    """
    N, M = dist_matrix.shape
    prob = LpProblem("regional_placement", LpMinimize)

    # Decision vars
    y = [LpVariable(f"y_{j}", cat=LpBinary) for j in range(M)]
    x = [[LpVariable(f"x_{i}_{j}", cat=LpBinary) for j in range(M)] for i in range(N)]

    # Objective: weighted latency + fixed costs
    prob += lpSum(weights[i] * dist_matrix[i, j] * x[i][j]
                  for i in range(N) for j in range(M)) + lpSum(costs[j] * y[j] for j in range(M))

    # Each site assigned to exactly one open region
    for i in range(N):
        prob += lpSum(x[i][j] for j in range(M)) == 1

    # Assignment only to opened region
    for i in range(N):
        for j in range(M):
            prob += x[i][j] <= y[j]

    # Capacity constraints
    for j in range(M):
        prob += lpSum(weights[i] * x[i][j] for i in range(N)) <= capacities[j] * y[j]

    # Solve with default CBC solver; adjust time/threads as needed
    prob.solve(PULP_CBC_CMD(msg=0, threads=4))

    selected = [j for j in range(M) if y[j].value() > 0.5]
    assignment = [next(j for j in range(M) if x[i][j].value() > 0.5) for i in range(N)]
    return selected, assignment

# Example usage omitted for brevity; integrate with measured RTTs and capacity sizing.