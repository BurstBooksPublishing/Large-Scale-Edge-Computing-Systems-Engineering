#!/bin/bash
# /usr/local/bin/start-ptp.sh
# Exit on error
set -euo pipefail

IFACE="eth0"                    # network interface with PTP-capable NIC
PTP_STACK="/usr/sbin/ptp4l"     # linuxptp ptp4l binary
PHC2SYS="/usr/sbin/phc2sys"     # sync PHC to system clock or vice versa
LOGDIR="/var/log/ptp"
CPU_CORE=2                      # isolate process to reduce jitter

mkdir -p "$LOGDIR"
# start ptp4l with hardware timestamping, gPTP profile for TSN integration
taskset -c $CPU_CORE $PTP_STACK -i "$IFACE" -m -A -2 -S -P \
  --profile gptp > "$LOGDIR/ptp4l.log" 2>&1 &

PTP_PID=$!
# small sleep to ensure PHC device exists (e.g., /dev/ptp0)
sleep 0.5

# find PHC device for interface (uses ethtool clock info)
PHC_DEV=$(ethtool -T $IFACE 2>/dev/null | awk '/PTP hardware clock/ {print "/dev/ptp" NR-1}')
# fallback if above does not work; user may set explicitly
PHC_DEV=${PHC_DEV:-/dev/ptp0}

# sync PHC to system clock with small polling interval; use -r for real-time priority
taskset -c $CPU_CORE $PHC2SYS -s CLOCK_REALTIME -c "$PHC_DEV" -r 0.1 \
  > "$LOGDIR/phc2sys.log" 2>&1 &

echo "ptp4l PID=$PTP_PID, PHC device=$PHC_DEV"