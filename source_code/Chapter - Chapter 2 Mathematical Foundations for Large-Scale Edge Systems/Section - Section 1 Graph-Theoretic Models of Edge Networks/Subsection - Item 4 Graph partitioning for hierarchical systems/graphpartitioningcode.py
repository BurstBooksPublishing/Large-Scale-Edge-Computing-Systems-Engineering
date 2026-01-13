# Production-ready: requires networkx and pymetis installed.
import networkx as nx
import pymetis

def build_weighted_graph(edges, node_caps, latency_factor=1.0, bw_factor=1.0):
    G = nx.Graph()
    for n,cap in node_caps.items():
        G.add_node(n, capacity=cap)
    for u,v,latency,bandwidth in edges:
        # combined edge cost; tune factors per SLA importance
        cost = latency_factor*latency + bw_factor*(1.0/max(bandwidth,1e-6))
        G.add_edge(u, v, weight=cost)
    return G

def part_graph_capacity_aware(G, nparts):
    # adjacency in PyMetis format
    node_list = list(G.nodes())
    idx = {n:i for i,n in enumerate(node_list)}
    adjacency = []
    adjwgt = []
    vwgt = [int(G.nodes[n].get('capacity',1)) for n in node_list]
    for n in node_list:
        nbrs = list(G[n].keys())
        adjacency.append([idx[v] for v in nbrs])
        adjwgt.append([int(G[n][v].get('weight',1)) for v in nbrs])
    # call PyMetis; returns (edgecuts, part_assignment)
    _, parts = pymetis.part_graph(nparts, adjacency=adjacency, adjwgt=adjwgt, vwgt=vwgt)
    return dict(zip(node_list, parts))

# Example usage: edges=(u,v,latency_ms,bandwidth_Mbps)
edges = [
    ('sensor1','gw1',5,50), ('sensor2','gw1',7,40), ('gw1','agg1',20,200),
    ('sensor3','gw2',6,30), ('gw2','agg1',25,150), ('agg1','cloud',100,1000)
]
node_caps = {'sensor1':1,'sensor2':1,'sensor3':1,'gw1':4,'gw2':4,'agg1':32,'cloud':1000}
G = build_weighted_graph(edges, node_caps)
assignment = part_graph_capacity_aware(G, nparts=3)
print(assignment)  # map node -> partition id for orchestration labels