/* Real-time control loop: compile with -lrt -pthread */
#include 
#include 
#include 
#include 
#include 
#include 
#include 
#include 
#include 

#define PERIOD_NS 1000000L   /* 1 kHz */
#define DEST_IP "192.168.1.100"
#define DEST_PORT 15000

static void set_realtime(pthread_t t, int prio, int cpu) {
    struct sched_param sp = {.sched_priority = prio};
    pthread_setschedparam(t, SCHED_FIFO, &sp);             /* set FIFO */
    cpu_set_t cp;
    CPU_ZERO(&cp); CPU_SET(cpu, &cp);
    pthread_setaffinity_np(t, sizeof(cp), &cp);           /* pin core */
}

static void send_priority_udp(int sock, struct sockaddr_in *dst, const void *buf, size_t len) {
    int tos = 0x2E;                                       /* DSCP for low-latency */
    setsockopt(sock, IPPROTO_IP, IP_TOS, &tos, sizeof(tos));
    sendto(sock, buf, len, 0, (struct sockaddr*)dst, sizeof(*dst));
}

void *control_thread(void *arg) {
    /* lock memory to prevent paging */
    mlockall(MCL_CURRENT | MCL_FUTURE);

    set_realtime(pthread_self(), 80, 1);                  /* high-priority on CPU1 */

    int sock = socket(AF_INET, SOCK_DGRAM, 0);
    struct sockaddr_in dst = {.sin_family = AF_INET, .sin_port = htons(DEST_PORT)};
    inet_pton(AF_INET, DEST_IP, &dst.sin_addr);

    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);

    while (1) {
        /* wake at aligned period (PTP preferred for absolute sync) */
        ts.tv_nsec += PERIOD_NS;
        if (ts.tv_nsec >= 1000000000L) { ts.tv_sec++; ts.tv_nsec -= 1000000000L; }
        /* perform sensor read and control compute (replace with real code) */
        char payload[64] = "control command";
        /* deterministic send with priority set above */
        send_priority_udp(sock, &dst, payload, sizeof(payload));
        /* sleep until next period */
        clock_nanosleep(CLOCK_MONOTONIC, TIMER_ABSTIME, &ts, NULL);
    }
    return NULL;
}

int main(void) {
    pthread_t t;
    pthread_create(&t, NULL, control_thread, NULL);
    pthread_join(t, NULL);
    return 0;
}