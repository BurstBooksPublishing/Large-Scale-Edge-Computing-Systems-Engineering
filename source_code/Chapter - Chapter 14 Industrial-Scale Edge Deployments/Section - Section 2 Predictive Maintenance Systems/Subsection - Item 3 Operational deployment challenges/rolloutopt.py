import math, requests, time

# Configuration (populate with real values)
MENDER_API = "https://hosted.mender.io/api/management/v1/deployments"
MENDER_TOKEN = "REPLACE_WITH_API_TOKEN"             # secure storage expected
N = 1000                                            # fleet size
r = 0.002                                           # per-device regression prob
t_b = 30.0                                          # minutes per batch
C_t = 50.0                                          # $ per minute
C_d = 400.0                                         # $ per affected device

def q(b):                                           # batch failure prob
    return 1.0 - (1.0 - r)**b

def expected_affected(b):
    qb = q(b)
    if qb == 0:
        return 0.0
    batches_to_detect = 1.0 / qb
    expected = b * min(batches_to_detect, math.ceil(N / b))
    return min(expected, N)

def total_cost(b):
    deploy_time_cost = math.ceil(N / b) * t_b * C_t
    return deploy_time_cost + expected_affected(b) * C_d

def find_optimal_b():
    best_b, best_cost = 1, float('inf')
    for b in range(1, min(200, N)+1):               # cap search for practicality
        c = total_cost(b)
        if c < best_cost:
            best_b, best_cost = b, c
    return best_b, best_cost

# Compute and perform staged rollout via Mender API (simplified)
def create_mender_deployment(artifact_name, group, batch_size):
    headers = {"Authorization": f"Bearer {MENDER_TOKEN}", "Content-Type": "application/json"}
    payload = {
        "name": f"staged-rollout-{artifact_name}",
        "artifact_name": artifact_name,
        "group": group,
        "max_devices": batch_size
    }
    # POST to Mender deployment endpoint (production code should handle errors, retries)
    r = requests.post(MENDER_API, json=payload, headers=headers, timeout=30)
    r.raise_for_status()
    return r.json()

if __name__ == "__main__":
    b, cost = find_optimal_b()
    print(f"optimal batch size: {b}, estimated cost: ${cost:,.2f}")
    # Example: create Mender deployments per batch (iterate groups or use pagination)
    # create_mender_deployment("predictive-model-v2", "region-west", b)