#include 
#include 
#include 
#include 
#include 
#include 
#include 
#include 

// Create non-blocking UDP socket, set QoS, large enough buffers, and use batching.
int create_latency_udp(const char *bind_ip, uint16_t port) {
    int fd = socket(AF_INET, SOCK_DGRAM | SOCK_NONBLOCK, 0);
    if (fd < 0) return -1;
    int prio = 6; // network priority for real-time control
    setsockopt(fd, SOL_SOCKET, SO_PRIORITY, &prio, sizeof(prio)); // requires CAP_NET_ADMIN
    int tos = 0x2E; // DSCP EF + small ECN capable marking
    setsockopt(fd, IPPROTO_IP, IP_TOS, &tos, sizeof(tos));
    // Resize kernel buffers to slightly above BDP; check return values in production.
    int rbuf = 8192, sndbuf = 8192;
    setsockopt(fd, SOL_SOCKET, SO_RCVBUF, &rbuf, sizeof(rbuf));
    setsockopt(fd, SOL_SOCKET, SO_SNDBUF, &sndbuf, sizeof(sndbuf));
    struct sockaddr_in sa = { .sin_family = AF_INET, .sin_port = htons(port) };
    inet_pton(AF_INET, bind_ip, &sa.sin_addr);
    if (bind(fd, (struct sockaddr*)&sa, sizeof(sa)) < 0) { close(fd); return -1; }
    return fd;
}

// Example send loop: build mmsghdr array and call sendmmsg to amortize syscalls.
// recv similarly with recvmmsg to get timestamps and batch packets.