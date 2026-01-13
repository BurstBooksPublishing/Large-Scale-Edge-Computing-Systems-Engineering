#!/usr/bin/env python3
# Lightweight probe to measure per-container resource overhead.
import os, subprocess, json, time
import psutil  # pip install psutil

RUNTIME = os.getenv("CONTAINER_RUNTIME", "docker")  # "docker" or "ctr"
# list containers: use docker API or containerd ctr
def list_containers():
    if RUNTIME == "docker":
        out = subprocess.check_output(["docker","ps","--format","{{.ID}} {{.Names}} {{.Image}}"]).decode()
        return [line.split() for line in out.strip().splitlines() if line]
    else:
        out = subprocess.check_output(["ctr","containers","list","--quiet"]).decode()
        return [[cid.strip()] for cid in out.strip().splitlines() if cid]
def inspect_docker(cid):
    j = json.loads(subprocess.check_output(["docker","inspect",cid]))
    pid = j[0]["State"]["Pid"]
    return pid, j[0]["Name"], j[0]["Config"]["Image"]
def proc_metrics(pid):
    p = psutil.Process(pid)
    mem = p.memory_info().rss  # bytes
    cpu = p.cpu_percent(interval=0.2)  # percent over short interval
    return mem, cpu
def gather():
    rows=[]
    for item in list_containers():
        try:
            if RUNTIME == "docker":
                pid,name,image = inspect_docker(item[0])
            else:
                # for containerd, map task -> pid via ctr t list (requires privileges)
                pid = int(subprocess.check_output(["ctr","tasks","pid",item[0]]))
                name = item[0]; image = "unknown"
            mem, cpu = proc_metrics(pid)
            rows.append({"id":item[0],"name":name,"image":image,"pid":pid,"mem_bytes":mem,"cpu_pct":cpu})
        except Exception as e:
            rows.append({"id":item[0],"error":str(e)})
    # aggregate node-level baseline
    total_mem = psutil.virtual_memory().used
    timestamp = int(time.time())
    payload = {"ts": timestamp, "node_used_mem": total_mem, "containers": rows}
    print(json.dumps(payload))  # send to stdout or push to collector
if __name__ == "__main__":
    gather()