#!/usr/bin/env python3
"""Convert the simulated one-beam front ToF LaserScan into sensor_msgs/Range."""

import math

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan, Range


class FrontToFRangeNode(Node):
    def __init__(self):
        super().__init__('front_tof_range_node')
        self.declare_parameter('scan_topic', '/tof/front/scan')
        self.declare_parameter('range_topic', '/tof/front/range')
        self.declare_parameter('frame_id', 'front_tof_link')

        scan_topic = self.get_parameter('scan_topic').value
        range_topic = self.get_parameter('range_topic').value
        self.frame_id = self.get_parameter('frame_id').value

        self.pub = self.create_publisher(Range, range_topic, 10)
        self.sub = self.create_subscription(
            LaserScan,
            scan_topic,
            self.scan_callback,
            10,
        )
        self.get_logger().info(
            'Front ToF range converter started: scan=%s range=%s frame=%s'
            % (scan_topic, range_topic, self.frame_id)
        )

    def scan_callback(self, msg):
        out = Range()
        out.header = msg.header
        if self.frame_id:
            out.header.frame_id = self.frame_id
        out.radiation_type = Range.INFRARED
        out.field_of_view = max(0.01, abs(msg.angle_max - msg.angle_min))
        out.min_range = float(msg.range_min)
        out.max_range = float(msg.range_max)

        finite_ranges = [
            float(value)
            for value in msg.ranges
            if math.isfinite(float(value))
        ]
        if finite_ranges:
            out.range = min(finite_ranges)
        else:
            out.range = float('inf')
        self.pub.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = FrontToFRangeNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
