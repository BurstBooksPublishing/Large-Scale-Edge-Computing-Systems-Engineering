#!/usr/bin/env bash
set -euo pipefail
IF=eth0                       # interface with TSN-capable NIC
PHC=/dev/ptp0                 # PHC device for NIC (check with `ethtool -T $IF`)
PTP_CONF=/etc/ptp4l.conf      # ptp4l config (domain, clockClass, etc.)

# start ptp4l (gPTP) in background; requires CAP_NET_ADMIN
nohup ptp4l -f "$PTP_CONF" -i "$IF" -m >/var/log/ptp4l.log 2>&1 &

# synchronize system clock to PHC
nohup phc2sys -s "$PHC" -w -m >/var/log/phc2sys.log 2>&1 &

# example taprio schedule: two windows, TC0 allowed for 200ms, TC1 for 800ms
# base-time should be in the future and aligned to PHC; adjust per deployment
BASE_TIME=$(($(date +%s%N) + 5_000_000_000))  # 5s in future (ns)
tc qdisc replace dev "$IF" root taprio num_tc 2 \
  map 0 1 \
  queues 1@0 1@1 \
  base-time $BASE_TIME \
  sched-entry S 1 200000000 S 2 800000000 \
  flags 0

# map VLAN PCP 5 to TC0 (low latency) and PCP 0 to TC1
# uses bridge ingress mapping; adjust per system bridge configuration
bridge vlan add dev "$IF" vid 0 pvid untagged
bridge vlan add dev "$IF" vid 100 pcp 5

echo "TSN base-time: $BASE_TIME; taprio installed on $IF"