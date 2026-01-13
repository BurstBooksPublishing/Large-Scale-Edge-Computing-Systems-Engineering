import asyncio
from asyncio_mqtt import Client, MqttError

# Production-ready: TLS config, reconnect backoff, and certificate validation required.
BROKER = "mec-controller.local"
CONTROL_TOPIC = "policies/edge/{node_id}"
HEARTBEAT = "heartbeat/{node_id}"

class PolicyAgent:
    def __init__(self, node_id, apply_cb):
        self.node_id = node_id
        self.apply_cb = apply_cb
        self.policy = {}                 # local policy cache

    async def run(self):
        reconnect_delay = 1
        while True:
            try:
                async with Client(BROKER) as client:
                    await client.subscribe(CONTROL_TOPIC.format(node_id=self.node_id))
                    await client.publish(HEARTBEAT.format(node_id=self.node_id), "online")
                    async with client.unfiltered_messages() as messages:
                        async for msg in messages:
                            await self._on_message(msg.topic, msg.payload.decode())
            except MqttError:
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(60, reconnect_delay*2)

    async def _on_message(self, topic, payload):
        # payload is JSON policy; validate signature and version in production.
        policy = payload  # deserialize in real code
        self.policy = policy
        await self.apply_cb(policy)      # apply locally with bounded latency

# Example apply callback
async def apply_policy(policy):
    # enforce policy in data plane (eBPF, firewall, or RTOS control)
    pass

if __name__ == "__main__":
    agent = PolicyAgent("rsu-123", apply_policy)
    asyncio.run(agent.run())