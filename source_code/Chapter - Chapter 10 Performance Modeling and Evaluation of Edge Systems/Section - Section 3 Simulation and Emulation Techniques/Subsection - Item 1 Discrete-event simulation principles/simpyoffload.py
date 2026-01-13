#!/usr/bin/env python3
"""
Edge offload DES using SimPy.
- Devices generate tasks (Poisson arrivals).
- Tasks either execute locally or offload to an edge node.
- Network delay modeled as Weibull to capture tails.
- Resources: SimPy Resource for device CPU and edge CPU.
"""
import simpy
import random
import statistics
from math import ceil
from scipy.stats import weibull_min  # production dependency

RNG = random.Random(42)

def weibull_delay(k, lam):
    # return one-way delay in seconds
    return weibull_min.rvs(c=k, scale=lam, random_state=RNG)

class EdgeSystem:
    def __init__(self, env, n_devices, device_mu, edge_mu, rtt_k, rtt_scale, offload_prob):
        self.env = env
        self.device_cpu = simpy.Resource(env, capacity=n_devices)  # local CPUs
        self.edge_cpu = simpy.Resource(env, capacity=4)            # edge node capacity
        self.device_mu = device_mu
        self.edge_mu = edge_mu
        self.rtt_k = rtt_k
        self.rtt_scale = rtt_scale
        self.offload_prob = offload_prob
        self.latencies = []

    def task_service(self, size, mu):
        # Exponential service time given service rate mu (jobs/sec)
        yield self.env.timeout(random.expovariate(mu))

    def handle_task(self, dev_id, task_id):
        arrival = self.env.now
        if RNG.random() < self.offload_prob:
            # Offload: send to edge, process, and return result
            send_delay = weibull_delay(self.rtt_k, self.rtt_scale)
            yield self.env.timeout(send_delay)  # one-way
            with self.edge_cpu.request() as req:
                yield req
                yield from self.task_service(size=1, mu=self.edge_mu)
            recv_delay = weibull_delay(self.rtt_k, self.rtt_scale)
            yield self.env.timeout(recv_delay)
        else:
            # Local execution
            with self.device_cpu.request() as req:
                yield req
                yield from self.task_service(size=1, mu=self.device_mu)
        self.latencies.append(self.env.now - arrival)

def device_generator(env, system, dev_id, lam):
    task_id = 0
    while True:
        inter = random.expovariate(lam)
        yield env.timeout(inter)
        env.process(system.handle_task(dev_id, task_id))
        task_id += 1

if __name__ == "__main__":
    # Parameters tuned for Raspberry Pi and Jetson-like profiles
    N_DEVICES = 50
    LAMBDA = 0.05          # per-device arrival rate (tasks/sec)
    DEVICE_MU = 0.2        # device service rate (jobs/sec)
    EDGE_MU = 5.0          # edge service rate (jobs/sec)
    RTT_K = 1.5
    RTT_SCALE = 0.02       # mean ~20 ms one-way
    OFFLOAD_P = 0.7

    env = simpy.Environment()
    sys = EdgeSystem(env, N_DEVICES, DEVICE_MU, EDGE_MU, RTT_K, RTT_SCALE, OFFLOAD_P)
    for d in range(N_DEVICES):
        env.process(device_generator(env, sys, d, LAMBDA))
    SIM_TIME = 3600  # simulate one hour
    env.run(until=SIM_TIME)

    print("Tasks simulated:", len(sys.latencies))
    print("Median latency (s):", statistics.median(sys.latencies))
    print("99th percentile (s):", statistics.quantiles(sys.latencies, n=100)[98])