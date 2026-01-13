from ortools.sat.python import cp_model

def solve_placement(tasks, nodes, cpu_req, cap, lat):
    # tasks: list of task ids; nodes: list of node ids
    # cpu_req[t], cap[n], lat[(n,m)] link latency matrix
    model = cp_model.CpModel()
    x = {}
    for t in tasks:
        for n in nodes:
            x[(t,n)] = model.NewBoolVar(f"x_{t}_{n}")  # placement var
    # each task placed exactly once
    for t in tasks:
        model.Add(sum(x[(t,n)] for n in nodes) == 1)
    # capacity constraints
    for n in nodes:
        model.Add(sum(cpu_req[t] * x[(t,n)] for t in tasks) <= cap[n])
    # minimize maximum pairwise latency (proxy for E2E); M bound chosen conservatively
    M = sum(lat.values()) + 1
    z = model.NewIntVar(0, M, "max_latency")
    for t in tasks:
        for s in tasks:
            if t == s:
                continue
            # linearize pairwise latency: sum_{n,m} lat_{n,m} * x_{t,n} * x_{s,m}
            # use intermediate IntVar with Big-M
            pair = model.NewIntVar(0, M, f"pair_{t}_{s}")
            # impose pair >= lat[n,m] - M*(2 - x_tn - x_sm) for all n,m
            for n in nodes:
                for m in nodes:
                    model.Add(pair >= int(lat[(n,m)]) - M * (2 - x[(t,n)] - x[(s,m)]))
            model.Add(pair <= z)  # enforce max
    model.Minimize(z)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    status = solver.Solve(model)
    feasible = status == cp_model.OPTIMAL or status == cp_model.FEASIBLE
    return feasible, { (t,n): solver.Value(x[(t,n)]) for t in tasks for n in nodes } if feasible else None

# Example uses: integrate with KubeEdge placement controller or offline planner.