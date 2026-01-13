from ortools.sat.python import cp_model

def solve_placement(apps, nodes, latency, demand, capacity, time_limit_ms=30000):
    # apps: list of app IDs
    # nodes: list of node IDs
    # latency[(a,n)]: estimated latency
    # demand[(a,r)]: demand per resource r
    # capacity[(n,r)]: capacity per node and resource r
    model = cp_model.CpModel()
    x = {}
    for a in apps:
        for n in nodes:
            x[a,n] = model.NewBoolVar(f"x_{a}_{n}")  # assign app a to node n
    # each app assigned exactly once
    for a in apps:
        model.Add(sum(x[a,n] for n in nodes) == 1)
    # capacity constraints per node and resource
    resources = set(r for (_,r) in demand.keys())
    for n in nodes:
        for r in resources:
            model.Add(
                sum(demand[a,r] * x[a,n] for a in apps) <= capacity[n,r]
            )
    # objective: minimize total latency (integer coefficients)
    model.Minimize(sum(int(latency[a,n]*1000) * x[a,n] for a in apps for n in nodes))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_ms / 1000.0
    solver.parameters.num_search_workers = 8  # tune to platform cores
    status = solver.Solve(model)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {a: next(n for n in nodes if solver.Value(x[a,n])==1) for a in apps}
    else:
        raise RuntimeError("No feasible assignment within time limit")

# Example invocation would supply real latency, demand, and capacity dicts.