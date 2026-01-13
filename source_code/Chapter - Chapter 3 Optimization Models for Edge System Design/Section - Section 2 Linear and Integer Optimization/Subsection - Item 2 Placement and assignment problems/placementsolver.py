from ortools.sat.python import cp_model

def solve_placement(tasks, nodes, weights, time_limit=10):
    """
    tasks: list of dicts with keys 'id','cpu','net','deadline'
    nodes: list of dicts with keys 'id','cpu_cap','bandwidth','proc_lat','cost'
    weights: dict with keys 'latency','cost'
    """
    model = cp_model.CpModel()
    x = {}  # x[(i,j)] binary assignment
    for i, t in enumerate(tasks):
        for j, n in enumerate(nodes):
            x[i, j] = model.NewBoolVar(f"x_{i}_{j}")
    # each task assigned exactly once
    for i in range(len(tasks)):
        model.Add(sum(x[i, j] for j in range(len(nodes))) == 1)
    # CPU and bandwidth capacity constraints
    for j, n in enumerate(nodes):
        model.Add(sum(tasks[i]['cpu'] * x[i, j] for i in range(len(tasks)))
                  <= n['cpu_cap'])
        model.Add(sum(tasks[i]['net'] * x[i, j] for i in range(len(tasks)))
                  <= n['bandwidth'])
    # deadline constraints: proc_lat + network <= deadline
    for i, t in enumerate(tasks):
        for j, n in enumerate(nodes):
            # linearize: if x_ij == 1 then latency constraint must hold
            model.Add(n['proc_lat'] + t['net'] <= t['deadline']).OnlyEnforceIf(x[i, j])
    # objective: weighted sum of latency and cost
    objective_terms = []
    for i, t in enumerate(tasks):
        for j, n in enumerate(nodes):
            lat = n['proc_lat'] + t['net']
            objective_terms.append(weights['latency'] * lat * x[i, j])
            objective_terms.append(weights['cost'] * n['cost'] * x[i, j])
    model.Minimize(sum(objective_terms))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("No feasible placement found")
    assignment = {}
    for i, t in enumerate(tasks):
        for j, n in enumerate(nodes):
            if solver.Value(x[i, j]):
                assignment[t['id']] = n['id']
    return assignment

# Example invocation omitted for brevity.