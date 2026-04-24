#!/usr/bin/env python3
"""Placeholder coverage executor node for future work."""

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node


class CoverageExecutorNode(Node):
    """Skeleton only: no movement or goal execution logic exists yet."""

    def __init__(self):
        super().__init__('coverage_executor_node')
        self.get_logger().info(
            'Coverage executor placeholder started; no goal execution is active.'
        )


def main(args=None):
    rclpy.init(args=args)
    node = CoverageExecutorNode()

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
