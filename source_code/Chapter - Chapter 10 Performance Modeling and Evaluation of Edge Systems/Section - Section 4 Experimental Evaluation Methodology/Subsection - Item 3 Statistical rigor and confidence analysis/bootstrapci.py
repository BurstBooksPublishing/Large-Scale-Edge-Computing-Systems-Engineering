#!/usr/bin/env python3
# production-ready: requirements numpy,pandas,scipy
import sys, argparse, math, numpy as np, pandas as pd
from scipy.stats import norm

def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument("csv", help="CSV with column 'latency_ms'")
    p.add_argument("--alpha", type=float, default=0.05)
    p.add_argument("--blocks", type=int, default=10, help="block length in samples")
    p.add_argument("--iters", type=int, default=10000)
    return p.parse_args()

def parametric_ci_mean(x, alpha=0.05):
    n=len(x); mu=x.mean(); s=x.std(ddof=1)
    z=norm.ppf(1-alpha/2)
    me=z*s/math.sqrt(n)
    return mu-me, mu+me

def block_bootstrap(x, stat_fn, block_len=10, iters=10000, seed=0):
    rng=np.random.default_rng(seed)
    n=len(x); nb=math.ceil(n/block_len)
    blocks=[x[i:i+block_len] for i in range(0,n,block_len)]
    bvals=[]
    for _ in range(iters):
        idx=rng.integers(0,len(blocks),size=nb)
        sample=np.concatenate([blocks[i] for i in idx])[:n]
        bvals.append(stat_fn(sample))
    return np.percentile(bvals, [100*2.5, 100*97.5])  # 95% CI

def main():
    args=parse_args()
    df=pd.read_csv(args.csv)
    x=df['latency_ms'].dropna().to_numpy()
    print("n=",len(x))
    ci_mean=parametric_ci_mean(x, args.alpha)
    print(f"Mean CI (parametric): {ci_mean[0]:.3f} ms - {ci_mean[1]:.3f} ms")
    median_ci=block_bootstrap(x, np.median, block_len=args.blocks, iters=args.iters, seed=42)
    p99_ci=block_bootstrap(x, lambda a: np.percentile(a,99), block_len=args.blocks, iters=args.iters, seed=43)
    print(f"Median CI (block bootstrap): {median_ci[0]:.3f} - {median_ci[1]:.3f} ms")
    print(f"99th CI (block bootstrap): {p99_ci[0]:.3f} - {p99_ci[1]:.3f} ms")

if __name__=="__main__":
    main()