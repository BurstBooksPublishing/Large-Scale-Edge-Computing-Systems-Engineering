from ortools.linear_solver import pywraplp

def solve_placement(functions, nodes, latency, cpu_need, cpu_capacity,
                    energy, cost, weights):
    # functions: list of function ids
    # nodes: list of node ids
    # latency[(f,n)], energy[(f,n)], cost[(f,n)] maps
    w_lat, w_eng, w_cost = weights

    solver = pywraplp.Solver.CreateSolver('CBC')
    x = {}
    # decision variables
    for f in functions:
        for n in nodes:
            x[f,n] = solver.IntVar(0, 1, f'x_{f}_{n}')

    # objective
    obj = solver.Objective()
    for f in functions:
        for n in nodes:
            coeff = w_lat*latency[(f,n)] + w_eng*energy[(f,n)] + w_cost*cost[(f,n)]
            obj.SetCoefficient(x[f,n], coeff)
    obj.SetMinimization()

    # each function assigned once
    for f in functions:
        solver.Add(solver.Sum(x[f,n] for n in nodes) == 1)

    # capacity constraints
    for n in nodes:
        solver.Add(solver.Sum(cpu_need[f]*x[f,n] for f in functions) <= cpu_capacity[n])

    status = solver.Solve()
    if status != pywraplp.Solver.OPTIMAL:
        raise RuntimeError('No optimal solution found')

    assignment = {f: next(n for n in nodes if x[f,n].solution_value()>0.5) for f in functions}
    return assignment

# Example usage comment: integrate with telemetry (prometheus) to populate latency, lambda rates, and CPU capacities.