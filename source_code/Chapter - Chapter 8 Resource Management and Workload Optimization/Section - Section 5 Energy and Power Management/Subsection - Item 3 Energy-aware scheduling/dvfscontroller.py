#!/usr/bin/env python3
# Minimal production DVFS controller: reads CPU load, computes freq, writes sysfs.
import os, time, logging, psutil, math, requests
LOG = logging.getLogger("dvfs")
logging.basicConfig(level=logging.INFO)

CPU_FREQ_PATH = "/sys/devices/system/cpu/cpu0/cpufreq"
AVAILABLE_PATH = os.path.join(CPU_FREQ_PATH, "scaling_available_frequencies")
SET_PATH = os.path.join(CPU_FREQ_PATH, "scaling_setspeed")  # requires root
SAMPLE_INTERVAL = 1.0
TAIL_PERCENTILE = 0.99
GAMMA = 0.1  # energy-latency tradeoff

def read_available_freqs():
    try:
        with open(AVAILABLE_PATH) as f:
            freqs = sorted({int(x) for x in f.read().split()})
        return freqs
    except Exception:
        return [600000, 1000000, 1400000, 1800000, 2200000]  # fallback

def estimate_required_freq(cpu_util, freqs):
    # Simple cost model: target service rate proportional to freq.
    # Map util to frequency linearly with headroom factor.
    headroom = max(1.0, 1.0 + 0.5*(cpu_util-0.7))
    target = int(min(freqs[-1], max(freqs[0], cpu_util*freqs[-1]*headroom)))
    # snap to nearest available frequency
    return min(freqs, key=lambda f: abs(f-target))

def set_frequency(freq):
    try:
        with open(SET_PATH, "w") as f:
            f.write(str(freq))
        LOG.info("Set freq %d", freq)
    except PermissionError:
        LOG.error("Requires root to write %s", SET_PATH)

def main_loop():
    freqs = read_available_freqs()
    util_history = []
    while True:
        util = psutil.cpu_percent(interval=SAMPLE_INTERVAL)/100.0
        util_history.append(util)
        if len(util_history) > 300:
            util_history.pop(0)
        tail = sorted(util_history)[int(len(util_history)*TAIL_PERCENTILE)]
        req_freq = estimate_required_freq(tail, freqs)
        set_frequency(req_freq)
        # optional: report state to cluster controller
        try:
            requests.post("http://127.0.0.1:8080/node/energy", json={"freq":req_freq,"tail":tail}, timeout=0.5)
        except Exception:
            pass

if __name__ == "__main__":
    main_loop()