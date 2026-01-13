#!/usr/bin/env python3
"""
risk_priotizer.py - load device inventory JSON, compute physical exposure risk,
and write a CSV with top-N remediation candidates.
"""
from dataclasses import dataclass
import json, csv, math, logging
from typing import List

logging.basicConfig(level=logging.INFO)

@dataclass
class Device:
    id: str
    lambda_rate: float     # attempts per hour
    tamper_rating: float   # unitless
    detect_delay_h: float  # hours
    weight: float          # criticality weight

def compromise_prob(dev: Device, alpha: float=0.8) -> float:
    # Eq. (1): p = 1 - exp(-lambda * e^{-alpha r} * t_d)
    lam_eff = dev.lambda_rate * math.exp(-alpha * dev.tamper_rating)
    return 1.0 - math.exp(-lam_eff * dev.detect_delay_h)

def load_inventory(path: str) -> List[Device]:
    with open(path, "r", encoding="utf-8") as f:
        items = json.load(f)
    return [Device(id=item["id"],
                   lambda_rate=float(item["lambda_rate"]),
                   tamper_rating=float(item["tamper_rating"]),
                   detect_delay_h=float(item["detect_delay_h"]),
                   weight=float(item.get("weight", 1.0)))
            for item in items]

def export_prioritized(devs: List[Device], out_csv: str, top_n: int=100):
    scored = [(d, compromise_prob(d)) for d in devs]
    scored.sort(key=lambda x: x[0].weight * x[1], reverse=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id","risk_score","compromise_prob","weight"])
        for d,p in scored[:top_n]:
            w.writerow([d.id, d.weight * p, f"{p:.6f}", f"{d.weight:.3f}"])
    logging.info("Exported top-%d risks to %s", top_n, out_csv)

if __name__ == "__main__":
    import sys
    inv = load_inventory(sys.argv[1])
    export_prioritized(inv, sys.argv[2], top_n=200)