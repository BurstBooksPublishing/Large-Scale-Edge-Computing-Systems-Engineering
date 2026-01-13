#!/usr/bin/env bash
# Production-ready nftables script: anti-spoof + basic policing
# Define allowed local subnets (adjust to site CIDRs)
nft add table inet filter
nft 'add set inet filter local_nets { type ipv4_addr\; flags interval\; }'
nft add element inet filter local_nets { 10.0.0.0/24, 192.168.100.0/24 }

# Base chains
nft 'add chain inet filter input { type filter hook input priority 0 ; }'
nft 'add chain inet filter forward { type filter hook forward priority 0 ; }'

# Drop invalid conntrack quickly
nft add rule inet filter input ct state invalid counter drop

# Anti-spoof: drop packets entering $if_edge with source not in local_nets
# Replace "eth0" with management/uplink interface
nft add rule inet filter forward iifname "eth0" ip saddr != @local_nets counter log prefix "ANTI_SPOOF: " drop

# Rate-limit ICMP and UDP to protect control-plane and prevent amplification
nft add rule inet filter forward icmp type echo-request limit rate 10/second burst 20 packets counter accept
nft add rule inet filter forward ip protocol udp limit rate 1000/second burst 200 packets counter accept

# Protect against DHCP starvation by limiting request rate on access ports
# Assume access ports map to interface names "port1", "port2"
nft add rule inet filter input iifname "port1" udp dport 67 limit rate 5/second burst 10 counter accept

# Allow established flows; default policy drop for forward chain recommended
nft add rule inet filter forward ct state established,related accept
nft set policy inet filter forward drop