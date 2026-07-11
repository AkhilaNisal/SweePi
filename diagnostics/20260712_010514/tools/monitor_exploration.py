#!/usr/bin/env python3
import hashlib
import json
import sys
import time

import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid, Odometry
from sensor_msgs.msg import LaserScan
from geometry_msgs.msg import Twist
from std_msgs.msg import String

class Monitor(Node):
    def __init__(self, duration):
        super().__init__('sweepi_exploration_diagnostic_monitor')
        self.duration = duration
        self.started = time.monotonic()
        self.latest = {}
        self.counts = {}
        self.map_stats = []
        self.create_subscription(LaserScan, '/scan', lambda m: self._seen('/scan', m), 10)
        self.create_subscription(Odometry, '/wheel/odom', lambda m: self._seen('/wheel/odom', m), 10)
        self.create_subscription(Odometry, '/odom', lambda m: self._seen('/odom', m), 10)
        self.create_subscription(Twist, '/cmd_vel', lambda m: self._cmd(m), 10)
        self.create_subscription(String, '/hardware/status', lambda m: self._seen('/hardware/status', m), 10)
        self.create_subscription(OccupancyGrid, '/map', lambda m: self._map('/map', m), 10)
        self.create_subscription(OccupancyGrid, '/slam_map', lambda m: self._map('/slam_map', m), 10)
        self.timer = self.create_timer(5.0, self._report)

    def _seen(self, topic, msg):
        self.latest[topic] = time.monotonic()
        self.counts[topic] = self.counts.get(topic, 0) + 1

    def _cmd(self, msg):
        self._seen('/cmd_vel', msg)
        self.latest['/cmd_vel_value'] = (float(msg.linear.x), float(msg.angular.z))

    def _map(self, topic, msg):
        self._seen(topic, msg)
        data = bytes((int(v) + 1) & 0xff for v in msg.data)
        unknown = sum(1 for v in msg.data if v < 0)
        free = sum(1 for v in msg.data if v == 0)
        occupied = sum(1 for v in msg.data if v > 0)
        digest = hashlib.sha256(data).hexdigest()[:16]
        stat = {
            't': round(time.monotonic() - self.started, 1),
            'topic': topic,
            'stamp_sec': int(msg.header.stamp.sec),
            'width': int(msg.info.width),
            'height': int(msg.info.height),
            'unknown': unknown,
            'free': free,
            'occupied': occupied,
            'hash': digest,
        }
        self.map_stats.append(stat)

    def _report(self):
        now = time.monotonic()
        ages = {}
        for topic, seen in self.latest.items():
            if topic.endswith('_value'):
                continue
            ages[topic] = round(now - seen, 3)
        print(json.dumps({
            'elapsed': round(now - self.started, 1),
            'counts': dict(self.counts),
            'ages': ages,
            'cmd_vel_value': self.latest.get('/cmd_vel_value'),
            'last_map_stats': self.map_stats[-4:],
        }), flush=True)
        if now - self.started >= self.duration:
            rclpy.shutdown()

def main():
    duration = float(sys.argv[1]) if len(sys.argv) > 1 else 60.0
    rclpy.init()
    node = Monitor(duration)
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()

if __name__ == '__main__':
    main()
