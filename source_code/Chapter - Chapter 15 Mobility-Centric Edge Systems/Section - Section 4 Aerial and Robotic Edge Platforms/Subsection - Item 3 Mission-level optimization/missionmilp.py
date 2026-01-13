# Production-ready MILP: OR-Tools, with time limit and solution export for MAVSDK/ROS2.
from ortools.linear_solver import pywraplp
import json, time

def solve_assignment(agents, tasks, cost_matrix, energy_required, time_limit_s=15):
    # agents: list of agent ids; tasks: list of task ids
    # cost_matrix[i][k] = weighted cost (energy+latency) for agent i doing task k
    solver = pywraplp.Solver.CreateSolver('CBC')
    solver.SetTimeLimit(int(time_limit_s*1000))
    x = {}
    for i,a in enumerate(agents):
        for k,t in enumerate(tasks):
            x[(i,k)] = solver.IntVar(0,1,f'x_{i}_{k}')
    # each task assigned to exactly one agent
    for k in range(len(tasks)):
        solver.Add(sum(x[(i,k)] for i in range(len(agents))) == 1)
    # per-agent energy constraint
    for i in range(len(agents)):
        solver.Add(sum(cost_matrix[i][k]['energy']*x[(i,k)] for k in range(len(tasks)))
                   <= energy_required[agents[i]])
    # objective: minimize sum(weighted_cost)
    obj = solver.Sum(x[(i,k)]*cost_matrix[i][k]['weighted']
                     for i in range(len(agents)) for k in range(len(tasks)))
    solver.Minimize(obj)
    status = solver.Solve()
    if status not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
        raise RuntimeError('No feasible assignment found')
    assignment = {}
    for i,a in enumerate(agents):
        assignment[a] = []
        for k,t in enumerate(tasks):
            if x[(i,k)].solution_value() > 0.5:
                assignment[a].append({'task': tasks[k],
                                      'energy': cost_matrix[i][k]['energy'],
                                      'latency': cost_matrix[i][k]['latency']})
    # export JSON for fleet manager / MAVSDK
    return json.dumps({'timestamp': time.time(), 'assignments': assignment})
# Example usage omitted for brevity.