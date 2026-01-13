#!/usr/bin/env python3
# Production-ready edge agent: active probes, EWMA estimation, tc shaping.
import asyncio, subprocess, logging, time
import iperf3  # pip install iperf3
logging.basicConfig(level=logging.INFO)

DEV='eth0'               # interface to shape
IP_TARGET='198.51.100.1' # probe target (MEC gateway)
ALPHA=0.25               # EWMA smoothing
BW_MIN=5e6               # minimum rate in bps to enforce (5 Mbps)

class State:
    def __init__(self):
        self.rtt=None
        self.bw=None

state=State()

async def ping_rtt(target):
    # run single ping, parse output for Linux ping
    proc=await asyncio.create_subprocess_exec('ping','-c','1','-W','1',target,
                                             stdout=asyncio.subprocess.PIPE)
    out=await proc.stdout.read()
    s=out.decode(errors='ignore')
    for line in s.splitlines():
        if 'time=' in line:
            return float(line.split('time=')[-1].split()[0])
    return None

def measure_iperf(target, duration=3):
    # synchronous iperf3 client for portability
    client=iperf3.Client()
    client.server_hostname=target
    client.duration=duration
    client.protocol='tcp'
    try:
        r=client.run()
        return r.sent_Mbps*1e6 if r.error is None else None
    except Exception as e:
        logging.debug('iperf error %s', e)
        return None

def ewma(prev, sample, alpha=ALPHA):
    if sample is None:
        return prev
    return sample if prev is None else alpha*sample + (1-alpha)*prev

def apply_tc(dev, rate_bps):
    # use token bucket filter to cap rate and limit queue size
    rate_kbit = max(int(rate_bps/1000), 1000)
    qlen = 50
    cmd=f'tc qdisc replace dev {dev} root tbf rate {rate_kbit}kbit burst 32kbit latency 50ms'
    subprocess.run(cmd, shell=True, check=False)
    logging.info('Applied tc: %s', cmd)

async def main_loop():
    while True:
        rtt = await ping_rtt(IP_TARGET)
        bw = measure_iperf(IP_TARGET, duration=2)
        state.rtt = ewma(state.rtt, rtt)
        state.bw  = ewma(state.bw, bw)
        logging.info('EWMA rtt=%.1f ms bw=%.1f Mbps', 
                     (state.rtt or 0.0), (state.bw or 0.0)/1e6)
        # control policy: if bw drops, reduce shaping to avoid build-up
        target_rate = max(state.bw*0.8 if state.bw else BW_MIN, BW_MIN)
        apply_tc(DEV, target_rate)
        await asyncio.sleep(5)

if __name__=='__main__':
    asyncio.run(main_loop())