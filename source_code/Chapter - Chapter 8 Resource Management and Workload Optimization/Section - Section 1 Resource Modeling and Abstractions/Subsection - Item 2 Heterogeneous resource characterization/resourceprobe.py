#!/usr/bin/env python3
# Production-ready probe: collects CPU, memory, network, and optional GPU info.
import json, subprocess, psutil, time, os

def cpu_info():
    return {
        "logical_cpus": psutil.cpu_count(logical=True),
        "physical_cpus": psutil.cpu_count(logical=False),
        "freq_current_mhz": psutil.cpu_freq().current
    }

def mem_info():
    vm = psutil.virtual_memory()
    return {"total_bytes": vm.total, "available_bytes": vm.available}

def net_info():
    # read interface speeds if available
    nets = {}
    for ifname, stats in psutil.net_if_stats().items():
        speed = stats.speed if stats.speed is not None else 0
        nets[ifname] = {"up": stats.isup, "speed_mbps": speed}
    return nets

def nvidia_info():
    try:
        out = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total,utilization.gpu,clocks.current.sm",
             "--format=csv,noheader,nounits"], text=True)
        gpus = []
        for line in out.strip().splitlines():
            name, mem, util, clk = [x.strip() for x in line.split(",")]
            gpus.append({"name": name, "mem_mb": int(mem), "util_percent": int(util), "sm_mhz": int(clk)})
        return gpus
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

def collect():
    return {
        "timestamp": int(time.time()),
        "node": os.uname().nodename,
        "cpu": cpu_info(),
        "memory": mem_info(),
        "network": net_info(),
        "nvidia_gpus": nvidia_info()
    }

if __name__ == "__main__":
    # print JSON to stdout for consumption by local agent or uploader
    print(json.dumps(collect()))