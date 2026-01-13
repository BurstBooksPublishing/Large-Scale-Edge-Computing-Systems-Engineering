import hashlib
import bisect
from confluent_kafka import Producer

class ConsistentPartitioner:
    def __init__(self, partitions, virtual_nodes=100, local_region=None):
        # partitions: list of int partition ids
        # virtual_nodes: virtual nodes per partition for smoothing
        self.ring = []               # sorted list of (hash, partition)
        self.partitions = partitions
        self.local_region = local_region
        for p in partitions:
            for v in range(virtual_nodes):
                key = f"{p}-{v}".encode()
                h = int(hashlib.md5(key).hexdigest(), 16)
                self.ring.append((h, p))
        self.ring.sort()

    def _hash(self, key_bytes):
        return int(hashlib.md5(key_bytes).hexdigest(), 16)

    def partition(self, key_bytes, event_meta=None):
        # event_meta may contain 'region' to prefer local partitions
        # First try region-preferring deterministic mapping
        if event_meta and event_meta.get("region")==self.local_region:
            local_key = b"LOCAL:" + key_bytes
            h = self._hash(local_key)
        else:
            h = self._hash(key_bytes)
        idx = bisect.bisect_right(self.ring, (h, float("inf")))
        if idx == len(self.ring):
            idx = 0
        return self.ring[idx][1]

# Usage in producer callback
def delivery_report(err, msg):
    if err:
        # handle retries, logging, or dead-letter routing
        print("Delivery failed:", err)

# instantiate with topic partitions discovered from broker metadata
partitions = [0,1,2,3,4]  # query via admin client in production
part = ConsistentPartitioner(partitions, local_region="eu-west-1")
p = Producer({'bootstrap.servers': 'broker:9092'})

key = b"sensor:1234"
meta = {"region": "eu-west-1"}
partition_id = part.partition(key, event_meta=meta)
p.produce("sensors", key=key, value=b"payload", partition=partition_id,
          on_delivery=delivery_report)
p.flush()