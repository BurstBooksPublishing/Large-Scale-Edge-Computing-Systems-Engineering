package placement

default allow = false

# Input contains workload and node catalog: input.workload, input.nodes
# Workload fields: id, required_gpu, max_latency_ms, weights.{latency,energy}
# Node fields: id, labels, gpu_count, avg_rtt_ms, energy_score (lower better)

# Hard constraint: reject if no node meets GPU or latency
violation[msg] {
  not some_node_available
  msg = sprintf("no available node satisfies hard constraints for %v", [input.workload.id])
}

some_node_available {
  node := input.nodes[_]
  node.gpu_count >= input.workload.required_gpu
  node.avg_rtt_ms <= input.workload.max_latency_ms
}

# Compute score for each node and sort
scores := sorted_nodes {
  scores = sort([node_score(n) | n := input.nodes[_] ], func(x,y) { x.score < y.score })
}

node_score(node) = { "node": node.id, "score": s } {
  # weighted linear combination, normalized measures expected in input
  w := input.workload.weights
  s := w.latency * node.avg_rtt_ms + w.energy * node.energy_score
}

# Admission decision: allow if at least one node passes hard constraints
allow = true {
  some_node_available
}

# Response returned to caller with violations or preferred node list
response := {"allowed": allow, "violations": [v | v := violation[_]], "preferred": [n.node | n := scores[0:3]]}