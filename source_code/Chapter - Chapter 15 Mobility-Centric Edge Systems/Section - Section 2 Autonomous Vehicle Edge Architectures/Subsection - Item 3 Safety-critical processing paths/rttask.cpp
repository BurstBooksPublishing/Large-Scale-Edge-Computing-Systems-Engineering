#include 
#include 
#include 
#include 
#include 

// Real-time task: hard-affinity, SCHED_FIFO, periodic loop, deadline detection.
static std::atomic run{true};

void set_realtime(pthread_t thr, int priority, int cpu) {
    sched_param param{.sched_priority = priority};
    pthread_setschedparam(thr, SCHED_FIFO, ¶m);             // RT priority
    cpu_set_t cpus; CPU_ZERO(&cpus); CPU_SET(cpu, &cpus);
    pthread_setaffinity_np(thr, sizeof(cpus), &cpus);           // bind CPU
}

void *safety_loop(void *) {
    const long period_ns = 20'000'000; // 20 ms period
    struct timespec next; clock_gettime(CLOCK_MONOTONIC, &next);
    while (run.load()) {
        // wait until next period
        next.tv_nsec += period_ns;
        while (next.tv_nsec >= 1'000'000'000) { next.tv_nsec -= 1'000'000'000; next.tv_sec++; }
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &next, nullptr);

        struct timespec before, after;
        clock_gettime(CLOCK_MONOTONIC, &before);

        // --- safety-critical processing stage (sensor->perception->plan) ---
        // call to pre-validated, WCET-profiled library (pseudo)
        // process_sensors(); run_perception(); compute_plan();

        clock_gettime(CLOCK_MONOTONIC, &after);
        long elapsed_us = (after.tv_sec - before.tv_sec)*1'000'000
                          + (after.tv_nsec - before.tv_nsec)/1000;
        // deadline monitoring and lightweight recovery action
        if (elapsed_us > 18'000) { // 18 ms soft deadline threshold
            // log and signal health manager; do not block in RT context
            std::cerr << "Deadline miss: " << elapsed_us << " us\n";
            // write to RT-safe telemetry or set heartbeat flag for watchdog
        }
    }
    return nullptr;
}

int main() {
    pthread_t thr;
    pthread_create(&thr, nullptr, safety_loop, nullptr);
    set_realtime(thr, /*priority=*/80, /*cpu=*/2);
    // system lifecycle: supervise, handle shutdown via health manager
    // ...
    run.store(false); pthread_join(thr, nullptr);
    return 0;
}