/* Simple P4_16 pipeline: parse Ethernet/IPv4, LPM table, INT counter, meter. */
/* Target-specific externs (clone, digest) may be required for Tofino. */

#include 

parser MyParser(packet_in pkt, out headers hdr) {
  state start {
    pkt.extract(hdr.ethernet);
    transition select(hdr.ethernet.etherType) {
      0x0800: parse_ipv4;
      default: accept;
    }
  }
  state parse_ipv4 {
    pkt.extract(hdr.ipv4);
    transition accept;
  }
}

control MyIngress(inout headers hdr, inout metadata meta, inout standard_metadata_t sm) {
  // LPM routing table: match on ipv4.dstAddr, action sets egress_port and next_hop.
  action set_nhop(bit<9> port, bit<32> nh_ip) {
    sm.egress_spec = port;
    meta.nh_ip = nh_ip;
  }

  table lpm_route {
    key = { hdr.ipv4.dstAddr: lpm; }
    actions = { set_nhop; drop; }
    size = 1024;
  }

  // simple in-line INT counter for telemetry aggregation
  action add_int() {
    meta.int_count = meta.int_count + 1; // target-dependent state possible
  }

  // token bucket meter per flow label
  meter flow_meter {
    @trusted = true;
    size = 1024;
    // meter config populated by control plane
  }

  apply {
    if (hdr.ipv4.isValid()) {
      lpm_route.apply();
      flow_meter.execute_meter(); // target extern
      add_int();
    }
  }
}

control MyEgress(...) { apply { } }
control MyDeparser(packet_out pkt, in headers hdr) { apply { pkt.emit(hdr.ethernet); if (hdr.ipv4.isValid()) pkt.emit(hdr.ipv4); } }

V1Switch(MyParser(), MyIngress(), MyEgress(), MyDeparser()) main;