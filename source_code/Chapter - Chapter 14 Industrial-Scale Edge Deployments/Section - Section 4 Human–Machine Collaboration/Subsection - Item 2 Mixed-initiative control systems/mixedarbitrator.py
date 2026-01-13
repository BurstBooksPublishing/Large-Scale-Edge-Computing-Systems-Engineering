#!/usr/bin/env python3
# Production-ready ROS2 rclpy node. Requires DDS security or TLS in transport.
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32, Bool
from geometry_msgs.msg import Twist
import math
import time

def sigmoid(x): return 1.0 / (1.0 + math.exp(-x))

class Arbitrator(Node):
    def __init__(self):
        super().__init__('mixed_arbitrator')
        # parameters tunable via ROS2 param server or orchestration
        self.declare_parameter('k_w', 1.0); self.declare_parameter('k_r', 2.0)
        self.declare_parameter('k_d', 5.0); self.declare_parameter('w0', 0.5)
        self.declare_parameter('r0', 0.7)
        # subscriptions: human cmd, auto cmd, risk, workload, latency estimate, watchdog
        self.sub_h = self.create_subscription(Twist, '/human_cmd', self.h_cb, 10)
        self.sub_a = self.create_subscription(Twist, '/auto_cmd', self.a_cb, 10)
        self.sub_r = self.create_subscription(Float32, '/risk_score', self.r_cb, 10)
        self.sub_w = self.create_subscription(Float32, '/workload', self.w_cb, 10)
        self.sub_d = self.create_subscription(Float32, '/latency_ms', self.d_cb, 10)
        self.sub_watch = self.create_subscription(Bool, '/hw_watchdog', self.wd_cb, 10)
        # publisher: actuators or low-level controller
        self.pub = self.create_publisher(Twist, '/cmd_actuator', 10)
        self.last_h = Twist(); self.last_a = Twist()
        self.risk=0.0; self.workload=0.0; self.latency=0.0; self.hw_ok=True
        self.timer = self.create_timer(0.02, self.tick)  # 50 Hz loop

    # callbacks update latest messages
    def h_cb(self, msg): self.last_h = msg
    def a_cb(self, msg): self.last_a = msg
    def r_cb(self, msg): self.risk = msg.data
    def w_cb(self, msg): self.workload = msg.data
    def d_cb(self, msg): self.latency = msg.data / 1000.0  # ms to s
    def wd_cb(self, msg): self.hw_ok = msg.data

    def compute_alpha(self):
        k_w = self.get_parameter('k_w').value
        k_r = self.get_parameter('k_r').value
        k_d = self.get_parameter('k_d').value
        w0 = self.get_parameter('w0').value
        r0 = self.get_parameter('r0').value
        x = k_w*(self.workload - w0) - k_r*(self.risk - r0) - k_d*self.latency
        return max(0.0, min(1.0, sigmoid(x)))

    def blend(self, a, b, alpha):
        out = Twist()
        out.linear.x = alpha*a.linear.x + (1-alpha)*b.linear.x
        out.angular.z = alpha*a.angular.z + (1-alpha)*b.angular.z
        return out

    def tick(self):
        if not self.hw_ok:
            # hardware-level failsafe: immediate stop
            stop = Twist()
            self.pub.publish(stop)
            return
        alpha = self.compute_alpha()
        cmd = self.blend(self.last_h, self.last_a, alpha)
        self.pub.publish(cmd)
        # minimal audit logging
        self.get_logger().debug(f'alpha={alpha:.3f} risk={self.risk:.2f} latency={self.latency:.3f}')

def main(args=None):
    rclpy.init(args=args)
    node = Arbitrator()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()