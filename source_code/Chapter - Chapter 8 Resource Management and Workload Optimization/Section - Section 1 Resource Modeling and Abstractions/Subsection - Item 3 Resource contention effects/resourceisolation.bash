#!/usr/bin/env bash
# Create cpuset for latency-critical process (use cgroup v1 cpuset mounted at /sys/fs/cgroup/cpuset)
CG=/sys/fs/cgroup/cpuset/real_time
mkdir -p "$CG"
echo 4-5 > "$CG"/cpuset.cpus              # reserve cores 4 and 5
echo 0 > "$CG"/cpuset.mems                 # restrict memory nodes (adjust per NUMA)
# Start process pinned into cgroup (PID after start moved into cgroup)
exec 1>&2
my_app --camera /dev/video0 &              # start app
sleep 0.2
echo $! > "$CG"/cgroup.procs               # move app into real_time cgroup

# Bind NIC IRQs to cores 0-3, avoid cores 4-5 reserved for real-time
for irq in $(grep -l "eth0" /proc/irq/*/smp_affinity | sed 's#/proc/irq/\([0-9]*\)/smp_affinity#\1#g'); do
  # set affinity mask for CPU0-3 (hex 0x0f)
  printf '%x' $((0x0f)) > /proc/irq/"$irq"/smp_affinity
done

# Apply egress bandwidth limit (1Gbps) on eth0 to prevent NIC burst squeezing the queue
tc qdisc replace dev eth0 root tbf rate 1gbit burst 32kbit latency 50ms

# Enable irqbalance off for consistency on real-time systems
systemctl stop irqbalance || true