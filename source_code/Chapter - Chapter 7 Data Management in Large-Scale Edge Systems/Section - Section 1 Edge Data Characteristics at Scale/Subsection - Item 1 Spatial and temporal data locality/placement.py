# Dependencies: numpy, sklearn
import numpy as np
from sklearn.cluster import KMeans

def place_edge_nodes(locations, weights, k, random_state=0):
    """
    locations: (N,2) array of float coordinates (e.g., UTM or lat/lon projected).
    weights: (N,) nonnegative request weights (aggregate demand).
    k: number of edge nodes to place.
    Returns: centers (k,2), assignments (N,), loads (k,)
    """
    # Normalize weights to avoid numerical issues
    w = np.array(weights, dtype=float)
    w_sum = w.sum()
    if w_sum == 0:
        raise ValueError("sum of weights must be > 0")
    w /= w_sum

    # Use KMeans++ with sample weighting
    kmeans = KMeans(n_clusters=k, init='k-means++', random_state=random_state)
    kmeans.fit(locations, sample_weight=w)
    centers = kmeans.cluster_centers_
    assignments = kmeans.labels_

    # Compute per-center load (sum of original weights)
    loads = np.zeros(k, dtype=float)
    for i, a in enumerate(assignments):
        loads[a] += weights[i]
    return centers, assignments, loads

# Example usage: sensor locations and hourly weights from telemetry
# centers, assign, loads = place_edge_nodes(sensor_coords, hourly_weights, k=8)