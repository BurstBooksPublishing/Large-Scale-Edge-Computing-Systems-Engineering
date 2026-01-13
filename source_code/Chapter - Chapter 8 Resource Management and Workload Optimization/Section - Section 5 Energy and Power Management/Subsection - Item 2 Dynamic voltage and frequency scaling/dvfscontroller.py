#!/usr/bin/env python3
import os, glob, time, math

CPU0_FREQ_PATH = '/sys/devices/system/cpu/cpu0/cpufreq'
# helper to read available frequencies (Hz)
def read_available_freqs():
    p = os.path.join(CPU0_FREQ_PATH, 'scaling_available_frequencies')
    if os.path.exists(p):
        s = open(p).read().strip()
        return sorted(int(x) for x in s.split())
    # fallback to governor-specific file
    p = os.path.join(CPU0_FREQ_PATH, 'scaling_policy0', 'scaling_available_frequencies')
    return sorted(int(x) for x in open(p).read().split())

def set_frequency(freq_hz):
    # set policy for all CPUs via policy directories
    for policy in glob.glob('/sys/devices/system/cpu/cpu*/cpufreq'):
        path = os.path.join(policy, 'scaling_setspeed')
        if os.path.exists(path):
            try:
                with open(path, 'w') as f:
                    f.write(str(freq_hz))
            except PermissionError:
                raise RuntimeError('Requires CAP_SYS_ADMIN')
    # optionally notify systemd or monitoring here

def nearest_opp(freqs, target):
    return min(freqs, key=lambda x: abs(x-target) if x>=target else float('inf'))

# main loop example: measure util (external) and enforce deadline
def controller_loop(deadline_s, measure_work_cycles):
    freqs = read_available_freqs()
    while True:
        W = measure_work_cycles()            # implement platform-specific perf counter
        f_req = math.ceil(W / deadline_s)    # cycles/s
        # choose minimal OPP >= f_req
        feasible = [f for f in freqs if f >= f_req]
        if not feasible:
            target = max(freqs)
        else:
            target = min(feasible)
        set_frequency(target)
        time.sleep(0.05)  # control interval; tune for transition latency

if __name__ == '__main__':
    # stub measure_work_cycles: use perf_event_open or platform counters in production
    controller_loop(0.1, lambda: 1_000_000_000)