#!/usr/bin/env python3
# Minimal, robust daemon: monitor RTTs and switch preferred route
import time, subprocess, logging
from pyroute2 import IPRoute

# configure endpoints and routes
WIRED_GW = '192.0.2.1'        # gateway reachable via eth0
WIRELESS_GW = '198.51.100.1'  # gateway reachable via wlan0
PREF_TABLE = 100              # policy routing table id
PING_COUNT = 3
CHECK_INTERVAL = 2.0

ip = IPRoute()
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

def ping_rtt(gw):
    # use system ping for robustness; returns median RTT in ms or None
    try:
        out = subprocess.check_output(
            ['ping', '-c', str(PING_COUNT), '-W', '1', gw],
            stderr=subprocess.DEVNULL, text=True)
        # parse rtt line like: rtt min/avg/max/mdev = ...
        for line in out.splitlines():
            if 'rtt' in line:
                parts = line.split('=')[1].split('/')
                return float(parts[1])
    except subprocess.CalledProcessError:
        return None

def set_preferred(gw_addr):
    # set default route in PREF_TABLE to chosen gateway
    # remove existing default in table
    for r in ip.get_default_routes(table=PREF_TABLE):
        ip.route('del', dst='default', table=PREF_TABLE,
                 gateway=r.get_attr('RTA_GATEWAY'))
    ip.route('add', dst='default', table=PREF_TABLE, gateway=gw_addr)
    # policy: use table for local source or fwmark as needed
    logging.info('Set preferred gateway %s in table %d', gw_addr, PREF_TABLE)

def main_loop():
    current = None
    while True:
        r_w = ping_rtt(WIRED_GW)
        r_wl = ping_rtt(WIRELESS_GW)
        logging.info('RTT wired=%s ms wireless=%s ms', r_w, r_wl)
        # simple decision rule: prefer lower RTT if reachable
        if r_w is None and r_wl is None:
            logging.warning('No path available')
        else:
            prefer = WIRED_GW if (r_w is not None and (r_wl is None or r_w < r_wl + 2.0)) else WIRELESS_GW
            if prefer != current:
                set_preferred(prefer)
                current = prefer
        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    main_loop()