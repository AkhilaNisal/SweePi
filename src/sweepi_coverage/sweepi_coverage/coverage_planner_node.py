#!/usr/bin/env python3
"""Placeholder coverage planner node for future Step 3 work."""

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node


class CoveragePlannerNode(Node):
    """Skeleton only: no planning logic is implemented yet."""

    def __init__(self):
        super().__init__('coverage_planner_node')
        self.get_logger().info(
            'Coverage planner placeholder started; no path planning is active.'
        )


def main(args=None):
    rclpy.init(args=args)
    node = CoveragePlannerNode()

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
