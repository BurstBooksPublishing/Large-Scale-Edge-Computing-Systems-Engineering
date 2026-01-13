from ortools.linear_solver import pywraplp

def robust_placement(cost, demand, cap, gamma, time_limit=30):
    # cost[i][j]: cost to place task i on node j
    # demand[i]: nominal demand of task i
    # cap[j]: capacity of node j
    # gamma: budgeted uncertainty (max tasks' demand growth)
    n, m = len(demand), len(cap)
    solver = pywraplp.Solver.CreateSolver('CBC')
    solver.set_time_limit(int(time_limit*1000))  # ms

    x = [[solver.IntVar(0, 1, f'x_{i}_{j}') for j in range(m)] for i in range(n)]
    # each task placed once
    for i in range(n):
        solver.Add(sum(x[i][j] for j in range(m)) == 1)

    # capacity constraints with worst-case extra demand up to gamma
    for j in range(m):
        # linearized worst-case: sum demand <= cap - max_extra
        # conservative approximation: assume gamma tasks can spike to max_ratio
        max_extra = gamma * max(demand)  # simple calibrated bound
        solver.Add(sum(demand[i]*x[i][j] for i in range(n)) <= cap[j] - max_extra)

    # objective
    obj = solver.Objective()
    for i in range(n):
        for j in range(m):
            obj.SetCoefficient(x[i][j], cost[i][j])
    obj.SetMinimization()

    status = solver.Solve()
    if status not in (solver.OPTIMAL, solver.FEASIBLE):
        raise RuntimeError('No feasible placement found')
    return {(i, j): int(x[i][j].solution_value()) for i in range(n) for j in range(m) if x[i][j].solution_value() > 0.5}

# Example invocation uses telemetry-derived arrays from Prometheus or edge agents.