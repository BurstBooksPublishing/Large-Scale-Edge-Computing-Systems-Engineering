#!/usr/bin/env python3
# Minimal controller to program OVS flows for local breakout.
import subprocess
import ipaddress

OVS_BRIDGE = "br-edge"           # OVS bridge on edge node
LOCAL_IFACE = "if-local-out"     # interface to local breakout/MEC
CORE_IFACE = "if-core-out"       # interface towards core/backhaul

def run(cmd):
    subprocess.run(cmd, shell=True, check=True)

def install_breakout(cidr, priority=100):
    # Match source or destination CIDR, output to LOCAL_IFACE
    net = ipaddress.ip_network(cidr)
    match = f"ip, nw_dst={net.network_address}/{net.prefixlen}"
    cmd = f"ovs-ofctl add-flow {OVS_BRIDGE} \"priority={priority},{match},actions=output:{LOCAL_IFACE}\""
    run(cmd)

def install_core_fallback(priority=50):
    # Default low-priority rule sends remaining traffic to core.
    cmd = f"ovs-ofctl add-flow {OVS_BRIDGE} \"priority={priority},ip,actions=output:{CORE_IFACE}\""
    run(cmd)

if __name__ == "__main__":
    # Example: steer AR/VR service subnet to local MEC
    install_breakout("10.10.100.0/24", priority=200)
    # Install fallback to core
    install_core_fallback()