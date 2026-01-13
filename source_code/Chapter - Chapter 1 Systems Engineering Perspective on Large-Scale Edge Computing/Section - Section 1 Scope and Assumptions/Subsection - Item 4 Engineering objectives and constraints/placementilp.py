from ortools.sat.python import cp_model

def solve_placement(I, J, L, E, s, C, wL=10, wE=1):
    model = cp_model.CpModel()
    x = {}
    # create boolean vars x[i,j]
    for i in I:
        for j in J:
            x[(i,j)] = model.NewBoolVar(f"x_{i}_{j}")
    # each flow assigned to exactly one node
    for i in I:
        model.Add(sum(x[(i,j)] for j in J) == 1)
    # capacity constraints
    for j in J:
        model.Add(sum(x[(i,j)] * s[i] for i in I) <= C[j])
    # objective: weighted latency + energy
    objective_terms = []
    for i in I:
        for j in J:
            # scale floats to integers if needed by CP-SAT
            coeff = int(wL * L[(i,j)] + wE * E[(i,j)])
            objective_terms.append(coeff * x[(i,j)])
    model.Minimize(sum(objective_terms))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0  # production knob
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {i: next(j for j in J if solver.Value(x[(i,j)]) == 1) for i in I}
    raise RuntimeError("No feasible assignment found")
# Caller supplies measured L, estimated E, sizes s, capacities C.