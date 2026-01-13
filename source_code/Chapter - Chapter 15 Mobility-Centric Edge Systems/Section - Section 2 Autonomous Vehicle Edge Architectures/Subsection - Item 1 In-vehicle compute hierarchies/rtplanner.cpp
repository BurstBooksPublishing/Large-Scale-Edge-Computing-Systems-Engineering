#include 
#include 
#include 
#include 
#include 
#include 
#include 
#include 
#include 
#include 

// Build: g++ -std=c++17 -O2 -pthread -o rt_planner rt_planner.cpp

void set_realtime(pthread_t t, int priority, int cpu) {
    sched_param param;
    param.sched_priority = priority;
    if (pthread_setschedparam(t, SCHED_FIFO, ¶m) != 0) {
        perror("pthread_setschedparam");
        exit(1);
    }
    cpu_set_t cpuset;
    CPU_ZERO(&cpuset);
    CPU_SET(cpu, &cpuset);
    if (pthread_setaffinity_np(t, sizeof(cpu_set_t), &cpuset) != 0) {
        perror("pthread_setaffinity_np");
        exit(1);
    }
}

int open_can(const char* ifname) {
    int s = socket(PF_CAN, SOCK_RAW, CAN_RAW);
    if (s < 0) { perror("socket"); exit(1); }
    struct ifreq ifr; std::strncpy(ifr.ifr_name, ifname, IFNAMSIZ);
    ioctl(s, SIOCGIFINDEX, &ifr);
    struct sockaddr_can addr;
    addr.can_family = AF_CAN;
    addr.can_ifindex = ifr.ifr_ifindex;
    if (bind(s, (struct sockaddr*)&addr, sizeof(addr)) < 0) { perror("bind"); exit(1); }
    return s;
}

void* planner_thread(void*) {
    // elevated priority and pinned CPU assigned from main
    int s = open_can("can0");
    struct can_frame frame;
    frame.can_id = 0x123; // CAN ID; bus scheduling uses ID priority (lower = higher priority)
    frame.can_dlc = 2;
    frame.data[0] = 0x01; // actuator command
    frame.data[1] = 0x00;
    while (true) {
        // compute control output (placeholder for deterministic planner)
        // send immediately to actuator bus
        if (write(s, &frame, sizeof(frame)) != sizeof(frame)) { perror("CAN write"); }
        usleep(10000); // 10 ms loop
    }
    return nullptr;
}

int main() {
    pthread_t t;
    pthread_create(&t, nullptr, planner_thread, nullptr);
    set_realtime(t, /*priority=*/80, /*cpu=*/1); // pin to core 1 with high SCHED_FIFO priority
    pthread_join(t, nullptr);
    return 0;
}