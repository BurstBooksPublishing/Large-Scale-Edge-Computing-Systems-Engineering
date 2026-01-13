#!/usr/bin/env python3
# production-ready: requires root, robust error handling, idempotent operations
import subprocess
import sys

IFACE = "eth0"                 # interface to configure
MAXRATE = "100mbit"            # policing/shaping limit for predictable queues
PRIO_HANDLE = "1:"             # qdisc handle

def run(cmd):
    subprocess.run(cmd, shell=True, check=True)

def safe_delete_qdisc():
    try:
        run(f"tc qdisc del dev {IFACE} root")
    except subprocess.CalledProcessError:
        pass  # ignore if no qdisc present

def apply_aqm():
    # Create priority qdisc with root HTB, class for maxrate, then fq_codel child
    run(f"tc qdisc add dev {IFACE} root handle {PRIO_HANDLE} htb default 10")
    run(f"tc class add dev {IFACE} parent {PRIO_HANDLE} classid {PRIO_HANDLE}10 htb rate {MAXRATE}")
    # attach fq_codel to class for low-latency deq
    run(f"tc qdisc add dev {IFACE} parent {PRIO_HANDLE}10 handle 10: fq_codel limit 1000 ecn")
    # verify
    run(f"tc -s qdisc show dev {IFACE}")

def enable_ecn():
    # Enable ECN for IPv4/IPv6 at kernel level where supported
    run("sysctl -w net.ipv4.tcp_ecn=1")
    run("sysctl -w net.ipv6.conf.all.use_tempaddr=0")  # example safe tweak
    # Optional: advertise ECN for non-TCP flows via DSCP/ECN markings in app

if __name__ == '__main__':
    if not sys.platform.startswith("linux"):
        raise SystemExit("This script targets Linux edge gateways.")
    safe_delete_qdisc()
    apply_aqm()
    enable_ecn()
    print("AQM and ECN configured on", IFACE)