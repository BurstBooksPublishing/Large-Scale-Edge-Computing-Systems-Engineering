import asyncio
import time
from opcua import Client  # pip install opcua-client
import rclpy
from rclpy.node import Node
from std_msgs.msg import String

DEADLINE_MS = 40  # maximum allowed end-to-end latency for supervisory command

class Supervisor(Node):
    def __init__(self, opcua_endpoint):
        super().__init__('supervisor')
        self.client = Client(opcua_endpoint)
        self.client.connect()  # persistent connection to PLC
        self.sub = self.create_subscription(10, String, self.callback)  # ROS2 QoS configured in real code

    def callback(self, msg):
        recv_ts = time.time()  # epoch seconds
        payload, sensor_ts = msg.data.split('|')  # "label|sensor_ts"
        sensor_ts = float(sensor_ts)
        latency_ms = (recv_ts - sensor_ts) * 1000
        if latency_ms > DEADLINE_MS:
            # deadline missed: log and optionally switch to safe param
            self.get_logger().warning(f'Deadline miss {latency_ms:.1f} ms')
            new_setpoint = self.safe_setpoint()
        else:
            new_setpoint = self.compute_setpoint(payload)
        # write setpoint atomically to PLC node
        self.client.get_node("ns=2;i=3001").set_value(float(new_setpoint))

    def compute_setpoint(self, label):
        # simple mapping; replace with ML-informed logic
        return 1.0 if label == 'defect' else 0.0

    def safe_setpoint(self):
        return 0.0

def main():
    rclpy.init()
    node = Supervisor("opc.tcp://192.168.0.20:4840")
    try:
        rclpy.spin(node)
    finally:
        node.client.disconnect()
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()