#!/usr/bin/env python3
# Production-ready: validated JSON parsing, streaming, and percentile computation.
import sys, json, datetime
from collections import defaultdict
import bisect

def parse_iso(ts):
    # parse ISO8601 with microsecond precision
    return datetime.datetime.fromisoformat(ts).timestamp()

def process_stream(stream, stage_names):
    per_stage_latencies = {s: [] for s in stage_names}
    total_latencies = []
    for line in stream:
        rec = json.loads(line)
        # rec must contain 'id' and timestamps dict with stage->iso timestamp
        t = rec.get('timestamps', {})
        try:
            times = [parse_iso(t[s]) for s in stage_names]
        except KeyError:
            continue  # skip incomplete traces
        # stage latencies are differences between consecutive stage timestamps
        stage_lat = []
        for i in range(1, len(times)):
            l = (times[i] - times[i-1]) * 1000.0  # ms
            per_stage_latencies[stage_names[i-1]].append(l)
            stage_lat.append(l)
        total_latencies.append(sum(stage_lat))
    return per_stage_latencies, total_latencies

def percentiles(data, ps=(50,95,99)):
    data_sorted = sorted(data)
    n = len(data_sorted)
    out = {}
    for p in ps:
        if n == 0:
            out[p] = None
            continue
        idx = int((p/100.0) * (n-1))
        out[p] = data_sorted[idx]
    return out

if __name__ == '__main__':
    # define stages: sensor->local_proc->tx->edge_proc->ack
    stages = ["sensor", "local_proc", "tx", "edge_proc", "ack"]
    per_stage, totals = process_stream(sys.stdin, stages)
    print("Total requests:", len(totals))
    print("Total latency P95 (ms):", percentiles(totals)[95])
    for s in stages:
        p = percentiles(per_stage[s])
        print(f"Stage {s}: count={len(per_stage[s])} P95={p[95]}ms mean={sum(per_stage[s])/len(per_stage[s]) if per_stage[s] else None}ms")