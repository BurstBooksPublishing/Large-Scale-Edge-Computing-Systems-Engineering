from ortools.sat.python import cp_model
from typing import List, Tuple, Dict

def placement_optimize(latency: List[List[float]],
                       energy: List[List[float]],
                       demand: List[float],
                       capacity: List[float],
                       weights: Tuple[float,float]) -> Dict[Tuple[int,int],int]:
    # latency, energy: matrices [num_tasks][num_nodes]
    # demand: per-task resource demand
    # capacity: per-node capacity
    # weights: (w_latency, w_energy) normalized externally
    num_tasks = len(latency)
    num_nodes = len(capacity)
    model = cp_model.CpModel()

    x = {}
    for i in range(num_tasks):
        for j in range(num_nodes):
            x[(i,j)] = model.NewBoolVar(f"x_{i}_{j}")

    # Each task assigned to exactly one node
    for i in range(num_tasks):
        model.Add(sum(x[(i,j)] for j in range(num_nodes)) == 1)

    # Capacity constraints
    for j in range(num_nodes):
        model.Add(sum(int(demand[i]*1000)*x[(i,j)] for i in range(num_tasks))
                  <= int(capacity[j]*1000))

    # Normalize latency and energy by max values to avoid scale issues
    max_lat = max(max(row) for row in latency) or 1.0
    max_eng = max(max(row) for row in energy) or 1.0

    # Linear objective coefficients as integers
    coeffs = {}
    for i in range(num_tasks):
        for j in range(num_nodes):
            coeffs[(i,j)] = int(
                weights[0]*(latency[i][j]/max_lat)*1000 +
                weights[1]*(energy[i][j]/max_eng)*1000
            )

    model.Minimize(sum(coeffs[(i,j)] * x[(i,j)] for i in range(num_tasks) for j in range(num_nodes)))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("No feasible placement found")

    assignment = {(i,j): int(solver.Value(x[(i,j)])) for i in range(num_tasks) for j in range(num_nodes)}
    return assignment

# Example usage integrated into orchestrator: compute assignment and translate to kube-scheduler hints or RTOS task bindings.