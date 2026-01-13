# Production-ready simulator: asyncio, numpy, logging
import asyncio, logging, time
import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orchestration_sim")

class EdgeNode:
    def __init__(self, idx, init_load):
        self.id = idx
        self.load = float(init_load)
    async def measure(self):
        await asyncio.sleep(0)                 # nonblocking sensor read
        return self.load

class HierarchicalController:
    def __init__(self, nodes, step=0.1, staleness_bound=2):
        self.nodes = nodes
        self.step = float(step)
        self.staleness_bound = int(staleness_bound)
        self.version = 0
        self.state_versions = {}               # node_id -> (version, load)
    async def poll_nodes(self):
        # asynchronous polls with simulated network jitter
        tasks = [node.measure() for node in self.nodes]
        loads = await asyncio.gather(*tasks)
        self.version += 1
        for n, l in zip(self.nodes, loads):
            # store versioned measurement
            self.state_versions[n.id] = (self.version, l)
    def compute_update(self):
        # simple proportional reconciliation toward mean load
        vs = list(self.state_versions.values())
        if not vs: return {}
        current_loads = np.array([v[1] for v in vs])
        mean = current_loads.mean()
        # compute deltas with step size and staleness check
        updates = {}
        for (node_id, (ver, load)) in zip([n.id for n in self.nodes], vs):
            age = self.version - ver
            if age > self.staleness_bound:
                continue                              # skip too-stale measurement
            delta = -self.step * (load - mean)       # migrate fraction
            updates[node_id] = delta
        return updates
    async def apply_updates(self, updates):
        # apply updates locally (simulation of migration)
        for n in self.nodes:
            if n.id in updates:
                n.load += updates[n.id]
async def run_simulation(N=6, steps=200, step=0.2):
    nodes = [EdgeNode(i, init_load=1.0 + 0.5*(i%3)) for i in range(N)]
    ctrl = HierarchicalController(nodes, step=step, staleness_bound=3)
    for t in range(steps):
        await ctrl.poll_nodes()
        updates = ctrl.compute_update()
        await ctrl.apply_updates(updates)
        if t % 10 == 0:
            loads = [round(n.load,3) for n in nodes]
            logger.info("t=%d loads=%s", t, loads)
        await asyncio.sleep(0.01)   # real-time pacing
if __name__ == "__main__":
    asyncio.run(run_simulation())