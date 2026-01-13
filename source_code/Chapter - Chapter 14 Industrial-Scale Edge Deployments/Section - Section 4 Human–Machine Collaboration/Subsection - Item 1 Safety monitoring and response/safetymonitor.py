# Python 3.9+, requires: asyncua, numpy, jetson_inference (or TRT wrapper)
import asyncio
import time
from asyncua import Client, ua
from inference import InferenceEngine  # production wrapper for TensorRT engine

# Configuration (inject via environment/config management)
CAMERA_URI = "rtsp://10.0.0.12/stream"
OPCUA_ENDPOINT = "opc.tcp://10.0.0.50:4840"
SAFETY_NODE_ID = "ns=2;i=2001"  # boolean node to trip safety relay
INFER_THRESHOLD = 0.6
HEARTBEAT_PERIOD = 0.5  # seconds
WATCHDOG_FILE = "/dev/watchdog"  # hardware watchdog device

async def plc_trip(client: Client):
    # atomic trip: write boolean True to safety node with server timestamp
    node = client.get_node(SAFETY_NODE_ID)
    await node.write_value(ua.DataValue(ua.Variant(True, ua.VariantType.Boolean),
                                       status=ua.StatusCode(ua.StatusCodes.Good),
                                       server_timestamp=ua.get_node_timestamp()))
    # logging and audit recorded elsewhere

async def monitor_loop(engine: InferenceEngine, opcua_client: Client):
    async with opcua_client:
        last_heartbeat = time.monotonic()
        async for frame in engine.stream_frames():  # yields preprocessed tensors
            start = time.monotonic()
            score = engine.infer_score(frame)  # returns hazard probability [0,1]
            if score >= INFER_THRESHOLD:
                # immediate, local emergency actuation (non-blocking)
                await plc_trip(opcua_client)
            # heartbeat to operator console or aggregator
            if time.monotonic() - last_heartbeat >= HEARTBEAT_PERIOD:
                engine.publish_heartbeat(score, latency=time.monotonic()-start)
                last_heartbeat = time.monotonic()

async def main():
    engine = InferenceEngine(CAMERA_URI, model_path="/opt/models/yolo.trt",
                             gpu_affinity=0, cpu_affinity=[1,2])
    opcua_client = Client(OPCUA_ENDPOINT, timeout=3.0)
    # open hardware watchdog to ensure system resets on software hang
    wd = open(WATCHDOG_FILE, "wb", buffering=0)
    try:
        task = asyncio.create_task(monitor_loop(engine, opcua_client))
        while True:
            wd.write(b'\0')          # kick hardware watchdog
            await asyncio.sleep(0.5)
    finally:
        wd.close()
        task.cancel()

if __name__ == "__main__":
    asyncio.run(main())