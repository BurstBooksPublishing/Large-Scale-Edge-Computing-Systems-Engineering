import math, json, time, sqlite3

class HoltOnline:
    def __init__(self, alpha=0.3, beta=0.05, gamma=0.01, node_capacity=2000):
        # alpha: level, beta: trend, gamma: variance smoothing
        self.alpha, self.beta, self.gamma = alpha, beta, gamma
        self.level = None
        self.trend = 0.0
        self.var = 1.0
        self.node_capacity = node_capacity

    def update(self, x):
        # x: new observation (e.g., msgs/min)
        if self.level is None:
            self.level = x
            self.trend = 0.0
            return
        prev_level = self.level
        # Holt equations (Eq. 1)
        self.level = self.alpha * x + (1 - self.alpha) * (self.level + self.trend)
        self.trend = self.beta * (self.level - prev_level) + (1 - self.beta) * self.trend
        # online variance (exponential smoothing of squared residual)
        resid = x - (prev_level + self.trend)
        self.var = self.gamma * (resid ** 2) + (1 - self.gamma) * self.var

    def forecast(self, h=1):
        # h-step ahead forecast (Eq. 1)
        if self.level is None:
            return 0.0, math.sqrt(self.var)
        mu = self.level + h * self.trend
        sigma = math.sqrt(self.var) * math.sqrt(h)  # approximate growth
        return mu, sigma

    def required_nodes(self, horizon=1, z=2.33):
        mu, sigma = self.forecast(horizon)
        required = math.ceil((mu + z * sigma) / self.node_capacity)
        return max(1, required)

    def save(self, path='holt_state.json'):
        with open(path, 'w') as f:
            json.dump({'level':self.level,'trend':self.trend,'var':self.var}, f)

    def load(self, path='holt_state.json'):
        with open(path) as f:
            d = json.load(f); self.level=d['level']; self.trend=d['trend']; self.var=d['var']

# Example usage: integrate with local aggregator or Prometheus exporter.