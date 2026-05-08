#!/usr/bin/env python3
"""Placeholder coverage manager node for future orchestration work."""

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node


class CoverageManagerNode(Node):
    """Skeleton only: no coverage state machine is implemented yet."""

    def __init__(self):
        super().__init__('coverage_manager_node')
        self.get_logger().info(
            'Coverage manager placeholder started; no coverage workflow is active.'
        )


def main(args=None):
    rclpy.init(args=args)
    node = CoverageManagerNode()

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
