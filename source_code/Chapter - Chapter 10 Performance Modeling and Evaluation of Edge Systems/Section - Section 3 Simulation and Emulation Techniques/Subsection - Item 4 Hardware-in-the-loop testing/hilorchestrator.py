#!/usr/bin/env python3
# Production-ready HIL orchestrator: requires Docker, pyroute2, prometheus_client.
import asyncio
import json
import time
from docker import DockerClient
from pyroute2 import IPRoute, NetNS, IPDB
from prometheus_client import CollectorRegistry, Gauge, push_to_gateway

GATEWAY_HOST = "gw.example.local"   # SSH/remote actions assumed via external system
CONTAINER_IMAGE = "edge-perception:latest"
PUSHGATEWAY = "pushgateway.example.local:9091"

async def configure_netem(ifname, delay_ms=50, loss_pct=0.1):
    # Use tc via pyroute2 or invoke 'tc qdisc' on the gateway; shown here as local helper.
    ip = IPRoute()
    idx = ip.link_lookup(ifname=ifname)[0]
    # Remove existing qdisc
    try:
        ip.tc("del", "qdisc", idx, "root")
    except Exception:
        pass
    # Add netem root qdisc with delay and loss
    ip.tc("add", "qdisc", idx, "root", "netem",
          {"latency": f"{delay_ms}ms", "loss": f"{loss_pct}%"})
    ip.close()

def start_container(image, cpu_set="0", mem_limit="1g"):
    client = DockerClient(base_url="unix://var/run/docker.sock")
    # Start container with pinned cpus and realtime-friendly settings
    container = client.containers.run(
        image,
        detach=True,
        tty=True,
        cpuset_cpus=cpu_set,
        mem_limit=mem_limit,
        network_mode="host",
        security_opt=["no-new-privileges"]
    )
    return container

def collect_timestamps(log_path="/var/log/hil_timestamps.json"):
    # Parse JSON lines produced by the workload with monotonic_ns timestamps
    latencies = []
    with open(log_path, "r") as f:
        for ln in f:
            rec = json.loads(ln)
            latencies.append(rec["actuator_ts"] - rec["sensor_ts"])
    return latencies

def push_metrics(latencies):
    reg = CollectorRegistry()
    g = Gauge('hil_latency_ms', 'HIL end-to-end latency', registry=reg)
    # push summary statistics
    mean_ms = sum(latencies)/len(latencies)/1e6
    g.set(mean_ms)
    push_to_gateway(PUSHGATEWAY, job='hil_test', registry=reg)

async def main():
    await configure_netem("eth0", delay_ms=100, loss_pct=0.5)  # apply impairment
    c = start_container(CONTAINER_IMAGE, cpu_set="2", mem_limit="2g")
    await asyncio.sleep(10)  # let system warm up
    # trigger test scenario (API call, GPIO toggles, etc.) omitted for brevity
    await asyncio.sleep(60)  # run for measurement window
    c.stop(timeout=10)
    lat = collect_timestamps("/var/log/hil_timestamps.json")
    push_metrics(lat)

if __name__ == "__main__":
    asyncio.run(main())