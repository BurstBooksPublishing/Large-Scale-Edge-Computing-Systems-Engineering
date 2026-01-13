#!/usr/bin/env python3
"""
tail_latency_analyzer.py
Reads CSV of events: start_timestamp_ns,end_timestamp_ns
Outputs p50,p95,p99,p99.9,mean,std,median_diff,p99-p50 as JSON.
"""
import sys
import csv
import json
from math import sqrt
from statistics import mean, stdev, median

def read_latencies(path):
    lat_ms = []
    with open(path, newline='') as f:
        r = csv.DictReader(f)
        for row in r:
            # expects columns 'start_ns' and 'end_ns'
            s = int(row['start_ns']); e = int(row['end_ns'])
            lat_ms.append((e - s) / 1e6)
    return lat_ms

def quantiles(sorted_vals, probs):
    n = len(sorted_vals)
    out = {}
    for p in probs:
        if n == 0:
            out[p] = None; continue
        # linear interpolation method
        idx = p * (n - 1)
        lo = int(idx); hi = min(lo + 1, n - 1)
        frac = idx - lo
        out[p] = sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac
    return out

def median_abs_diff(vals):
    if len(vals) < 2:
        return 0.0
    diffs = [abs(vals[i] - vals[i-1]) for i in range(1, len(vals))]
    return median(diffs)

def analyze(path):
    lats = read_latencies(path)
    if not lats:
        return {}
    lats.sort()
    q = quantiles(lats, [0.5, 0.95, 0.99, 0.999])
    stats = {
        "count": len(lats),
        "mean_ms": mean(lats),
        "std_ms": stdev(lats) if len(lats) > 1 else 0.0,
        "p50_ms": q[0.5],
        "p95_ms": q[0.95],
        "p99_ms": q[0.99],
        "p99_9_ms": q[0.999],
        "median_diff_ms": median_abs_diff(lats),
        "p99_p50_ms": q[0.99] - q[0.5]
    }
    return stats

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: tail_latency_analyzer.py trace.csv", file=sys.stderr); sys.exit(1)
    result = analyze(sys.argv[1])
    print(json.dumps(result, indent=2))