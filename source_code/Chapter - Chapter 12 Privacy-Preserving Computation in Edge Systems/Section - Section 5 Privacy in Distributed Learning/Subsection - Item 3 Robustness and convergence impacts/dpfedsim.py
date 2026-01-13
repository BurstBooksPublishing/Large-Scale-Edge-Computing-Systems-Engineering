import numpy as np

# Server-side configuration
eta = 0.01                          # global learning rate
num_clients = 200
expected_K = 50
dp_sigma = 0.5                      # DP noise std dev (per-client)
dropout_prob = 0.2
model = np.zeros(100)               # example linear model (100 dims)

def client_update(model, data_X, data_y, lr=0.1, local_epochs=1):
    # simple SGD on linear MSE, returns delta (model_new - model)
    w = model.copy()
    for _ in range(local_epochs):
        preds = data_X.dot(w)
        grad = data_X.T.dot(preds - data_y) / data_X.shape[0]
        w -= lr * grad
    return w - model

def secure_aggregate(updates):
    # placeholder: real deployment should call a secure-aggregation library
    return sum(updates)             # server sees only sum

# Simulate one round
def federated_round(model, client_data):
    updates = []
    for X, y in client_data:
        if np.random.rand() < dropout_prob:
            continue
        delta = client_update(model, X, y)
        # local anomaly filter: simple norm threshold (runs on-device)
        if np.linalg.norm(delta) > 10.0:
            continue
        # add DP noise before transmission (client-side DP)
        noise = np.random.normal(scale=dp_sigma, size=delta.shape)
        updates.append(delta + noise)
    if not updates:
        return model
    agg = secure_aggregate(updates) / len(updates)
    model_new = model + eta * agg
    return model_new

# Example synthetic client data creation omitted for brevity.