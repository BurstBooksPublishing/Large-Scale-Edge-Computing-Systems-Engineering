#!/usr/bin/env python3
# Production-ready: queries Prometheus, computes Ochiai, outputs top-N causes.
import requests
from typing import Dict, Tuple

PROM_URL = "http://prometheus.example.local/api/v1/query_range"
QUERY = 'inference_failure_count{job=~"edge.*"}'  # adjust to deployment labels

def query_prometheus(query: str, start: str, end: str, step: str) -> dict:
    params = {"query": query, "start": start, "end": end, "step": step}
    r = requests.get(PROM_URL, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def compute_counts(series: dict) -> Dict[str, Tuple[int,int]]:
    # returns mapping component -> (n_f, n_p)
    counts = {}
    for item in series.get("data", {}).get("result", []):
        comp = item["metric"].get("component", "unknown")
        vals = item["values"]
        n_f = sum(1 for t,v in vals if float(v) > 0)
        n_p = sum(1 for t,v in vals if float(v) == 0)
        counts[comp] = (n_f, n_p)
    return counts

def ochiai_scores(counts: Dict[str, Tuple[int,int]]) -> Dict[str,float]:
    Nf = sum(nf for nf, np in counts.values())
    scores = {}
    for comp, (nf, np) in counts.items():
        denom = (Nf * (nf + np)) ** 0.5 if (nf + np) > 0 else 0.0
        scores[comp] = (nf / denom) if denom > 0 else 0.0
    return scores

if __name__ == "__main__":
    # example time window; in production, derive from alert timestamp
    resp = query_prometheus(QUERY, start="1672502400", end="1672506000", step="60")
    counts = compute_counts(resp)
    scores = ochiai_scores(counts)
    for comp, s in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:10]:
        print(f"{comp}: {s:.3f}")