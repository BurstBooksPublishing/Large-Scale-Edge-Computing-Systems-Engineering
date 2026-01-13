from ortools.sat.python import cp_model

def solve_placement(functions, nodes, cpu_req, cpu_cap, latency, must_host=None, max_replicas=None):
    # functions: list of function ids
    # nodes: list of node ids
    # cpu_req[f], cpu_cap[n]: dicts of CPU demand and capacity
    # latency[(f,n)]: client-to-node latency weight for function f to node n
    model = cp_model.CpModel()
    x = {}
    for f in functions:
        for n in nodes:
            x[f,n] = model.NewBoolVar(f"assign_{f}_{n}")
    # single-assignment (or at-least-one if replica allowed)
    for f in functions:
        if max_replicas and max_replicas.get(f,1) > 1:
            model.Add(sum(x[f,n] for n in nodes) <= max_replicas[f])
            model.Add(sum(x[f,n] for n in nodes) >= 1)  # ensure at least one replica
        else:
            model.Add(sum(x[f,n] for n in nodes) == 1)
    # CPU capacity constraints
    for n in nodes:
        model.Add(sum(cpu_req[f]*x[f,n] for f in functions) <= cpu_cap[n])
    # must_host constraints (e.g., regulatory)
    if must_host:
        for f, allowed_nodes in must_host.items():
            model.Add(sum(x[f,n] for n in allowed_nodes) == 1)
    # objective: minimize total weighted latency
    obj_terms = []
    for f in functions:
        for n in nodes:
            obj_terms.append(latency[(f,n)] * x[f,n])
    model.Minimize(sum(obj_terms))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return {(f,n): solver.Value(x[f,n]) for f in functions for n in nodes}
# Example usage omitted for brevity.