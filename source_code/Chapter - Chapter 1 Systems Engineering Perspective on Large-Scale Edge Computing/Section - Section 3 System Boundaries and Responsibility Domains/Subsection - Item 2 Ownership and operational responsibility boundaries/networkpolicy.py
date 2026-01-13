#!/usr/bin/env python3
# Minimal production-ready generator: reads CSV inventory and emits NetworkPolicy YAML.
# Requires: pyyaml; integrate with pipeline to kubectl apply.

import csv
import sys
import yaml
from collections import defaultdict

# Read CSV: node,namespace,owner
inv_path = sys.argv[1] if len(sys.argv)>1 else "inventory.csv"
owners = defaultdict(set)
with open(inv_path) as f:
    for row in csv.DictReader(f):
        # fields: node,namespace,owner
        owners[row['owner']].add(row['namespace'])

policies = []
for owner, namespaces in owners.items():
    # Allow intra-owner traffic; deny others by omission.
    for ns in namespaces:
        np = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {"name": f"deny-external-{owner}-{ns}", "namespace": ns},
            "spec": {
                "podSelector": {},  # all pods in namespace
                "policyTypes": ["Ingress","Egress"],
                "ingress": [
                    {"from": [{"namespaceSelector": {"matchLabels": {"owner": owner}}}]}
                ],
                "egress": [
                    {"to": [{"namespaceSelector": {"matchLabels": {"owner": owner}}}]}
                ]
            }
        }
        policies.append(np)

# Emit multi-doc YAML
print(yaml.dump_all(policies, sort_keys=False))