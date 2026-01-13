#!/usr/bin/env python3
"""
Apply timestamped network impairments (from ns-3) to Docker containers.
Assumes: docker SDK installed, 'ip' and 'tc' available on host, PTP/time sync ensured.
"""
import time, subprocess, json
import docker

client = docker.from_env()
# map logical node -> container name
NODE_TO_CONTAINER = {"edge-node-1":"edge_node_1", "edge-node-2":"edge_node_2"}

def run_in_netns(container_name, cmd):
    # run command inside the container network namespace
    cid = client.containers.get(container_name).id
    ns_cmd = ["nsenter", "-t", subprocess.check_output(["docker", "inspect", "-f", "{{.State.Pid}}", cid]).decode().strip(), "-n"] + cmd
    subprocess.check_call(ns_cmd)

def apply_netem(container_name, iface, delay_ms=0, loss_pct=0, rate_kbit=None):
    cmd = ["tc", "qdisc", "replace", "dev", iface, "root", "netem"]
    if delay_ms: cmd += ["delay", f"{delay_ms}ms"]
    if loss_pct: cmd += ["loss", f"{loss_pct}%"]
    if rate_kbit:
        # add tbf for rate limiting if required
        run_in_netns(container_name, ["tc", "qdisc", "replace", "dev", iface, "root", "tbf", "rate", f"{rate_kbit}kbit",
                                      "burst", "32kbit", "latency", "400ms"])
    run_in_netns(container_name, cmd)

def replay_impairments(events_file):
    with open(events_file) as f:
        events = json.load(f)  # list of {ts, node, iface, delay_ms, loss_pct, rate_kbit}
    start = time.time()
    for ev in events:
        wall_target = start + ev["ts"]  # ts in seconds relative to start
        sleep = wall_target - time.time()
        if sleep>0: time.sleep(sleep)
        apply_netem(NODE_TO_CONTAINER[ev["node"]], ev["iface"], ev.get("delay_ms",0), ev.get("loss_pct",0), ev.get("rate_kbit"))

if __name__ == "__main__":
    replay_impairments("/var/sim/ns3_impairments.json")