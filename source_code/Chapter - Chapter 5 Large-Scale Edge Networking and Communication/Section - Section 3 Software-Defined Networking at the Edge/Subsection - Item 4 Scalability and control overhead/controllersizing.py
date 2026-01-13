#!/usr/bin/env python3
"""
Compute minimal controller instances/cores for given edge topology.
Accepts JSON config with fields: switches, lambda_per_switch,
core_capacity, target_util (0.0-0.9), slices (replication factor).
"""
import argparse, json, math, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)

def compute_required_cores(N: int, lam: float, mu: float, target_util: float, slices: int = 1):
    # Effective event rate per switch includes slice replication
    effective_lambda = lam * slices
    total_rate = N * effective_lambda
    # conservative core capacity at target utilization
    core_capacity_target = mu * target_util
    if core_capacity_target <= 0:
        raise ValueError("Invalid core capacity or target utilization")
    cores = math.ceil(total_rate / core_capacity_target)
    achieved_util = total_rate / (cores * mu)
    return cores, achieved_util, total_rate

def main():
    p = argparse.ArgumentParser()
    p.add_argument("config", type=Path, help="JSON config file")
    args = p.parse_args()
    cfg = json.loads(args.config.read_text())
    cores, util, total = compute_required_cores(
        N=int(cfg["switches"]),
        lam=float(cfg["lambda_per_switch"]),
        mu=float(cfg["core_capacity"]),
        target_util=float(cfg.get("target_util", 0.7)),
        slices=int(cfg.get("slices", 1))
    )
    logging.info("Total incoming events/s: %.1f", total)
    logging.info("Required controller cores/instances: %d", cores)
    logging.info("Projected utilization per core: %.2f", util)

if __name__ == "__main__":
    main()