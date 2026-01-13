/* iso_latency.c: compile with -O2 -lrt -pthread */
#define _GNU_SOURCE
#include 
#include 
#include 
#include 
#include 
#include 

static inline long timespec_to_ns(const struct timespec *t){
    return t->tv_sec*1000000000L + t->tv_nsec;
}

void *worker(void *arg){
    struct sched_param sp = {.sched_priority = 80};
    pthread_setschedparam(pthread_self(), SCHED_FIFO, &sp); // set RT scheduling
    cpu_set_t cp;
    CPU_ZERO(&cp); CPU_SET(1, &cp); // pin to CPU 1
    pthread_setaffinity_np(pthread_self(), sizeof(cp), &cp);

    struct timespec next;
    clock_gettime(CLOCK_MONOTONIC, &next);
    const long period_ns = 1000000L; // 1 ms period
    for(int i=0;i<100000;i++){
        next.tv_nsec += period_ns;
        if(next.tv_nsec >= 1000000000L){ next.tv_sec++; next.tv_nsec -= 1000000000L; }
        struct timespec before, after;
        clock_gettime(CLOCK_MONOTONIC, &before);
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &next, NULL);
        clock_gettime(CLOCK_MONOTONIC, &after);
        long jitter = timespec_to_ns(&after) - timespec_to_ns(&next);
        printf("%d %ld\n", i, jitter); // analyze distribution offline
    }
    return NULL;
}

int main(){
    pthread_t t;
    pthread_create(&t, NULL, worker, NULL);
    pthread_join(t, NULL);
    return 0;
}