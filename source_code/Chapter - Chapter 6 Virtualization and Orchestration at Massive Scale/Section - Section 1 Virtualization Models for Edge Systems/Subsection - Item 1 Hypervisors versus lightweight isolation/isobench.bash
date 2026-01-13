#!/usr/bin/env bash
set -euo pipefail

IMAGE=${1:-"alpine:3.18"}          # minimal image
ITER=${2:-20}                      # iterations per mode
OUTFILE=${3:-iso_bench_results.csv}

# Ensure docker available
command -v docker >/dev/null || { echo "docker required"; exit 1; }

printf "mode,iter,start_ns,end_ns,duration_ns,rss_kb\n" > "$OUTFILE"

measure() {
  local mode=$1
  for i in $(seq 1 $ITER); do
    # start timestamp (ns)
    t0=$(date +%s%N)
    # run container, execute sleep 0.1 to force short-lived process
    if [ "$mode" = "container" ]; then
      cid=$(docker run --rm -d "$IMAGE" sleep 0.1)
    else
      # kata-runtime must be registered as a Docker runtime with name 'kata-runtime'
      cid=$(docker run --rm -d --runtime=kata-runtime "$IMAGE" sleep 0.1)
    fi
    t1=$(date +%s%N)
    dur=$((t1 - t0))
    # get RSS from /sys/fs/cgroup for the created container (best-effort)
    # use docker inspect to map to pid then /proc/pid/statm
    pid=$(docker inspect --format '{{.State.Pid}}' "$cid" 2>/dev/null || echo 0)
    rss_kb=0
    if [ "$pid" -gt 0 ]; then
      # resident pages * page size (kB)
      pages=$(awk '{print $2}' /proc/"$pid"/statm 2>/dev/null || echo 0)
      page_kb=$(( $(getconf PAGE_SIZE) / 1024 ))
      rss_kb=$((pages * page_kb))
    fi
    printf "%s,%d,%s,%s,%d,%d\n" "$mode" "$i" "$t0" "$t1" "$dur" "$rss_kb" >> "$OUTFILE"
    # small delay to allow cleanup
    sleep 0.05
  done
}

measure container
measure kata
echo "Results written to $OUTFILE"